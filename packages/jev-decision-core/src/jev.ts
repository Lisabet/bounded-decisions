/** Typed Jev protocol transport. Caller owns task policy, accounting and retries. */
export type JsonObject = Record<string, unknown>;
export type JevRequest = {
  model: string;
  state: unknown;
  questions: Record<string, { type: 'choice'; instructions: string; criteria: Record<string, string> }>;
};
export type JevUsage = { input_tokens?: number; output_tokens?: number };
export type JevNormalizedResult = {
  requestedModel: string;
  /** Safe response metadata retained across copies and durable normalization. */
  responseStatus?: number;
  returnedModel?: string;
  answers?: Record<string, unknown>;
  usage?: JevUsage;
  usageInvalid?: boolean;
  observedBilledCostRub?: number;
  billingHeaderInvalid?: boolean;
  /** Optional caller-calculated estimate; kept separate from observed provider billing. */
  estimatedCostRub?: number;
};
export type JevTransportErrorCode = 'ROUTE'|'TRANSPORT'|'TIMEOUT'|'HTTP'|'BODY_LIMIT'|'INPUT_LIMIT'|'INVALID_RESPONSE';
export type JevBillingEvidence = {
  observedBilledCostRub?: number;
  billingHeaderInvalid?: boolean;
  observedBilledCurrency?: 'RUB';
  billedCostProvenance?: 'PlusVibe x-pv-cost-rub response header';
};
type JevErrorEvidence = JevBillingEvidence & { status?: number };
export class JevTransportError extends Error {
  readonly code:JevTransportErrorCode; readonly status?:number; readonly retryAfterMs?:number;
  readonly uncertain:boolean;
  readonly observedBilledCostRub?:number; readonly billingHeaderInvalid?:boolean;
  readonly observedBilledCurrency?:'RUB'; readonly billedCostProvenance?:'PlusVibe x-pv-cost-rub response header';
  constructor(code: JevTransportErrorCode, status?: number, retryAfterMs?: number, evidence?:JevErrorEvidence) {
    super(code); this.name = 'JevTransportError';
    this.code=code;this.status=status??evidence?.status;this.retryAfterMs=retryAfterMs;
    this.uncertain=code==='TIMEOUT'||code==='TRANSPORT';
    this.observedBilledCostRub=evidence?.observedBilledCostRub;
    this.billingHeaderInvalid=evidence?.billingHeaderInvalid;
    this.observedBilledCurrency=evidence?.observedBilledCurrency;
    this.billedCostProvenance=evidence?.billedCostProvenance;
  }
  toJSON(){return {name:this.name,message:this.message,code:this.code,...(this.status!==undefined?{status:this.status}:{}),...(this.retryAfterMs!==undefined?{retryAfterMs:this.retryAfterMs}:{}),uncertain:this.uncertain,...(this.observedBilledCostRub!==undefined?{observedBilledCostRub:this.observedBilledCostRub}:{}),...(this.billingHeaderInvalid!==undefined?{billingHeaderInvalid:this.billingHeaderInvalid}:{}),...(this.observedBilledCurrency?{observedBilledCurrency:this.observedBilledCurrency}:{}),...(this.billedCostProvenance?{billedCostProvenance:this.billedCostProvenance}:{})};}
}
export type JevTransportOptions = {
  url: URL;
  apiKey: string;
  fetchImpl: typeof fetch;
  timeoutMs: number;
  maxRequestBytes?: number;
  maxResponseBytes?: number;
};

const encode = (value: unknown) => JSON.stringify(value);
const bytes = (value: string) => new TextEncoder().encode(value).length;
const validObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const billingEvidence=(header:string|null):JevBillingEvidence=>{
  if(header===null)return {};
  const cost=Number(header);
  const common={observedBilledCurrency:'RUB' as const,billedCostProvenance:'PlusVibe x-pv-cost-rub response header' as const};
  if(!/^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/.test(header.trim())||!Number.isFinite(cost)||cost<0)return {...common,billingHeaderInvalid:true};
  return {...common,observedBilledCostRub:cost};
};
const responseEvidence=(response:Response,billing:JevBillingEvidence):JevErrorEvidence=>({status:response.status,...billing});
const invalidResult=(result:JevNormalizedResult):never=>{
  const inferred:JevErrorEvidence={
    ...(Number.isInteger(result.responseStatus)&&result.responseStatus!>=100&&result.responseStatus!<=599?{status:result.responseStatus}:{}),
    ...(result.observedBilledCostRub!==undefined?{observedBilledCostRub:result.observedBilledCostRub,observedBilledCurrency:'RUB',billedCostProvenance:'PlusVibe x-pv-cost-rub response header'}:{}),
    ...(result.billingHeaderInvalid?{billingHeaderInvalid:true,observedBilledCurrency:'RUB',billedCostProvenance:'PlusVibe x-pv-cost-rub response header'}:{}),
  };
  throw new JevTransportError('INVALID_RESPONSE',undefined,undefined,inferred);
};

/** Performs exactly one POST; retry, reservations, deadlines and interpretation belong to the caller. */
export async function postJevOnce(request: JevRequest, options: JevTransportOptions): Promise<JevNormalizedResult> {
  if (!request || typeof request.model!=='string'||!request.model.trim()||!options.apiKey || !Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0 || options.url.protocol !== 'https:' && !['localhost','127.0.0.1','[::1]'].includes(options.url.hostname)) throw new JevTransportError('ROUTE');
  const allowedRequest:JevRequest={model:request.model,state:request.state,questions:Object.create(null)};
  if(request.state===undefined||!validObject(request.questions)||Object.keys(request.questions).length===0)throw new JevTransportError('INVALID_RESPONSE');
  // Validate the actual JSON state, including toJSON/omission behavior, before transport.
  try { allowedRequest.state=JSON.parse(JSON.stringify(request.state)); } catch { throw new JevTransportError('INVALID_RESPONSE'); }
  const state=allowedRequest.state;
  if(!(typeof state==='string'&&state.trim()||Array.isArray(state)&&state.length||validObject(state)&&Object.keys(state).length))throw new JevTransportError('INVALID_RESPONSE');
  for(const [id,raw] of Object.entries(request.questions)){
    if(!id||!validObject(raw)||raw.type!=='choice'||typeof raw.instructions!=='string'||!raw.instructions||!validObject(raw.criteria)||Object.keys(raw.criteria).length<2||Object.entries(raw.criteria).some(([key,value])=>!key||typeof value!=='string'||!value))throw new JevTransportError('INVALID_RESPONSE');
    allowedRequest.questions[id]={type:'choice',instructions:raw.instructions,criteria:Object.fromEntries(Object.entries(raw.criteria)) as Record<string,string>};
  }
  for(const limit of [options.maxRequestBytes,options.maxResponseBytes])if(limit!==undefined&&(!Number.isSafeInteger(limit)||limit<=0))throw new JevTransportError('ROUTE');
  let body: string;
  try { body = encode(allowedRequest); if (typeof body !== 'string') throw new Error(); }
  catch { throw new JevTransportError('INVALID_RESPONSE'); }
  if (bytes(body) > (options.maxRequestBytes ?? 160_000)) throw new JevTransportError('INPUT_LIMIT');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs);
  let response: Response;
  try {
    response = await options.fetchImpl(options.url, { method:'POST', redirect:'error', signal:controller.signal,
      headers:{ authorization:`Bearer ${options.apiKey}`, 'content-type':'application/json' }, body });
  } catch { clearTimeout(timer); throw new JevTransportError(controller.signal.aborted ? 'TIMEOUT' : 'TRANSPORT'); }
  const billing=billingEvidence(response.headers.get('x-pv-cost-rub'));
  const evidence=responseEvidence(response,billing);
  if (!response.ok) {
    clearTimeout(timer); await response.body?.cancel().catch(()=>{});
    const raw=response.headers.get('retry-after'); let after=0;
    if(raw){const seconds=Number(raw);after=Number.isFinite(seconds)?Math.max(0,seconds*1000):Math.max(0,Date.parse(raw)-Date.now());}
    throw new JevTransportError('HTTP', response.status, after, evidence);
  }
  let raw: string;
  try {
    const reader=response.body?.getReader(); if(!reader)throw new JevTransportError('INVALID_RESPONSE',response.status,undefined,evidence);
    const chunks:Uint8Array[]=[];let size=0;
    while(true){let part:ReadableStreamReadResult<Uint8Array>;try{part=await reader.read();}catch{throw new JevTransportError(controller.signal.aborted?'TIMEOUT':'TRANSPORT',response.status,undefined,evidence);}const {done,value}=part;if(done)break;size+=value.byteLength;if(size>(options.maxResponseBytes??1024*1024)){await reader.cancel();throw new JevTransportError('BODY_LIMIT',response.status,undefined,evidence);}chunks.push(value);}
    const joined=new Uint8Array(size);let at=0;for(const chunk of chunks){joined.set(chunk,at);at+=chunk.byteLength;}
    raw=new TextDecoder('utf-8',{fatal:true}).decode(joined);
  } catch(error) { if(error instanceof JevTransportError)throw error; throw new JevTransportError(controller.signal.aborted?'TIMEOUT':'INVALID_RESPONSE',response.status,undefined,evidence); }
  finally { clearTimeout(timer); }
  let envelope: unknown; try { envelope=JSON.parse(raw); } catch { throw new JevTransportError('INVALID_RESPONSE',response.status,undefined,evidence); }
  if(!validObject(envelope))throw new JevTransportError('INVALID_RESPONSE',response.status,undefined,evidence);
  const usage=validObject(envelope.usage)?envelope.usage:undefined;
  const model=typeof envelope.model==='string'&&envelope.model?envelope.model:undefined;
  const answers=validObject(envelope.answers)?envelope.answers:undefined;
  const observedBilledCostRub=billing.observedBilledCostRub;
  const billingHeaderInvalid=!!billing.billingHeaderInvalid;
  const cleanUsage:JevUsage|undefined=usage?{
    ...(Number.isSafeInteger(usage.input_tokens)&&Number(usage.input_tokens)>=0?{input_tokens:Number(usage.input_tokens)}:{}),
    ...(Number.isSafeInteger(usage.output_tokens)&&Number(usage.output_tokens)>=0?{output_tokens:Number(usage.output_tokens)}:{}),
  }:undefined;
  const usageInvalid=envelope.usage!==undefined&&(!usage||(['input_tokens','output_tokens'] as const).some(key=>usage[key]!==undefined&&(!Number.isSafeInteger(usage[key])||Number(usage[key])<0)));
  const normalized={ requestedModel:request.model,responseStatus:response.status, ...(model?{returnedModel:model}:{}), ...(answers?{answers:answers as Record<string,unknown>}:{ }), ...(cleanUsage?{usage:cleanUsage}:{}), ...(usageInvalid?{usageInvalid:true}:{}), ...(observedBilledCostRub!==undefined?{observedBilledCostRub}:{}),...(billingHeaderInvalid?{billingHeaderInvalid:true}:{}) };
  return normalized;
}

/** Strict reusable response validator; project adapters may apply an explicit compatibility policy instead. */
export function validateJevResult(result:JevNormalizedResult,request:JevRequest):void{
  if(result.requestedModel!==request.model||typeof result.returnedModel!=='string'||result.returnedModel!==request.model)throw invalidResult(result);
  if(!validObject(result.answers)||Object.keys(result.answers).length!==Object.keys(request.questions).length)throw invalidResult(result);
  for(const [id,question] of Object.entries(request.questions)){
    const answer=result.answers[id];if(!validObject(answer)||answer.type!==undefined&&answer.type!=='choice'||typeof answer.choice!=='string'||!Object.hasOwn(question.criteria,answer.choice))throw invalidResult(result);
    if(answer.probabilities!==undefined){const probabilities=answer.probabilities;if(!validObject(probabilities)||Object.keys(probabilities).length!==Object.keys(question.criteria).length||Object.keys(question.criteria).some(k=>!Number.isFinite(probabilities[k])||Number(probabilities[k])<0||Number(probabilities[k])>1)||Math.abs(Object.values(probabilities).reduce<number>((sum,value)=>sum+Number(value),0)-1)>0.02)throw invalidResult(result);}
    if(answer.confidence!==undefined&&(!Number.isFinite(answer.confidence)||Number(answer.confidence)<0||Number(answer.confidence)>1))throw invalidResult(result);
  }
  if(result.usageInvalid||result.usage&&Object.values(result.usage).some(value=>!Number.isSafeInteger(value)||Number(value)<0))throw invalidResult(result);
  if(result.observedBilledCostRub!==undefined&&(!Number.isFinite(result.observedBilledCostRub)||result.observedBilledCostRub<0)||result.billingHeaderInvalid)throw invalidResult(result);
  if(result.estimatedCostRub!==undefined&&(!Number.isFinite(result.estimatedCostRub)||Number(result.estimatedCostRub)<0))throw invalidResult(result);
}
