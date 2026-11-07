import test from 'node:test';
import assert from 'node:assert/strict';
import {postJevOnce,validateJevResult,JevTransportError,type JevRequest} from '../src/jev.ts';

const model='synthetic/model';
const request:JevRequest={model,state:{text:'synthetic'},questions:{decision:{type:'choice',instructions:'Choose from the supplied options.',criteria:{alpha:'First option',beta:'Second option',insufficient:'Insufficient evidence'}}}};
const options=(fetchImpl:typeof fetch,extra:Partial<{maxRequestBytes:number;maxResponseBytes:number}>={})=>({url:new URL('https://example.invalid/v1/decisions'),apiKey:'synthetic-key',fetchImpl,timeoutMs:500,...extra});
const envelope={model,answers:{decision:{type:'choice',choice:'alpha',probabilities:{alpha:1,beta:0,insufficient:0},confidence:.9}},usage:{input_tokens:4,output_tokens:2}};

test('transport allowlists request and nested question keys before serialization',async()=>{
  let sent='';const noisy={...request,expected:'answer',cache_context:{secret:'local'},questions:{decision:{...request.questions.decision,private:'metadata'}}} as any;
  const normalized=await postJevOnce(noisy,options(async(_url,init)=>{sent=String(init?.body);return new Response(JSON.stringify(envelope),{headers:{'x-pv-cost-rub':'0.25'}});}));
  assert.equal(sent,JSON.stringify(request));assert.equal(normalized.requestedModel,model);assert.equal(normalized.returnedModel,model);assert.deepEqual(normalized.usage,{input_tokens:4,output_tokens:2});assert.equal(normalized.observedBilledCostRub,.25);
  validateJevResult(normalized,request);
});
test('strict core validates identities, answer keys, optional probabilities and confidence',async()=>{
  const good=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope))));validateJevResult(good,request);
  for(const changed of [{...envelope,model:'other'},{...envelope,answers:{other:envelope.answers.decision}},{...envelope,answers:{decision:{...envelope.answers.decision,probabilities:{alpha:.2,beta:.2,insufficient:.2}}}},{...envelope,answers:{decision:{...envelope.answers.decision,confidence:2}}}]){
    const normalized=await postJevOnce(request,options(async()=>new Response(JSON.stringify(changed))));assert.throws(()=>validateJevResult(normalized,request),JevTransportError);
  }
});
test('strict core accepts each of nine synthetic option IDs',async()=>{
  const criteria=Object.fromEntries(Array.from({length:9},(_,i)=>[`option_${i+1}`,`Synthetic option ${i+1}`]));
  const nine:JevRequest={model,state:{sample:'synthetic'},questions:{q:{type:'choice',instructions:'Choose one synthetic option.',criteria}}};
  for(const choice of Object.keys(criteria)){
    const body={model,answers:{q:{choice,probabilities:Object.fromEntries(Object.keys(criteria).map(id=>[id,id===choice?1:0]))}},usage:{input_tokens:0,output_tokens:0}};
    const normalized=await postJevOnce(nine,options(async()=>new Response(JSON.stringify(body))));validateJevResult(normalized,nine);
  }
});
test('optional observations remain absent in the normalized core',async()=>{
  const normalized=await postJevOnce(request,options(async()=>new Response(JSON.stringify({answers:{decision:{choice:'alpha'}}}))));
  assert.equal(normalized.usage,undefined);assert.equal(normalized.returnedModel,undefined);assert.equal(normalized.observedBilledCostRub,undefined);
});
test('strict core preserves malformed usage and estimate evidence for rejection',async()=>{
  for(const usage of [{input_tokens:-1,output_tokens:2},{input_tokens:'bad',output_tokens:2},null,'bad']){
    const normalized=await postJevOnce(request,options(async()=>new Response(JSON.stringify({...envelope,usage}))));
    assert.equal(normalized.usageInvalid,true);assert.throws(()=>validateJevResult(normalized,request),JevTransportError);
  }
  const normalized=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope))));
  assert.throws(()=>validateJevResult({...normalized,estimatedCostRub:Number.NaN},request),JevTransportError);
});
test('empty question sets are rejected and arbitrary own question IDs survive the allowlist',async()=>{
 let posts=0;
 await assert.rejects(postJevOnce({...request,questions:{}},options(async()=>{posts++;return new Response('{}');})),JevTransportError);
 assert.equal(posts,0);
 const special={...request,questions:Object.fromEntries([['__proto__',request.questions.decision]])};
 await postJevOnce(special,options(async(_url,init)=>{assert.ok(Object.hasOwn(JSON.parse(String(init?.body)).questions,'__proto__'));return new Response(JSON.stringify({model,answers:{}}));}));
});
test('factual state must survive JSON serialization and remain nonempty',async()=>{
 for(const state of [undefined,null,{},[],' ',0,()=>1,Symbol('local'),{toJSON:()=>undefined}]){
  let posts=0;await assert.rejects(postJevOnce({...request,state},options(async()=>{posts++;return new Response('{}');})),JevTransportError);assert.equal(posts,0);
 }
});
test('explicit refusal stays a rejected result with exactly one transport operation',async()=>{
 let posts=0;
 const value=await postJevOnce(request,options(async()=>{posts++;return new Response(JSON.stringify({model,refusal:'unsupported',usage:{input_tokens:0,output_tokens:0}}));}));
 assert.throws(()=>validateJevResult(value,request),JevTransportError);assert.equal(posts,1);
});
test('invalid billed header stays distinct from missing billed observation',async()=>{
  const normalized=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope),{headers:{'x-pv-cost-rub':' '}})));
  assert.equal(normalized.observedBilledCostRub,undefined);assert.equal(normalized.billingHeaderInvalid,true);assert.throws(()=>validateJevResult(normalized,request),JevTransportError);
});
test('malformed response, request and response limits use safe structural errors',async()=>{
  await assert.rejects(postJevOnce(request,options(async()=>new Response('private provider body'))),(e:any)=>e instanceof JevTransportError&&e.code==='INVALID_RESPONSE'&&!e.message.includes('private'));
  await assert.rejects(postJevOnce(request,options(async()=>new Response('{}'),{maxRequestBytes:5})),(e:any)=>e instanceof JevTransportError&&e.code==='INPUT_LIMIT');
  await assert.rejects(postJevOnce(request,options(async()=>new Response('x'.repeat(20)),{maxResponseBytes:5})),(e:any)=>e instanceof JevTransportError&&e.code==='BODY_LIMIT');
});
test('HTTP retry metadata and uncertain transport state are structural',async()=>{
  await assert.rejects(postJevOnce(request,options(async()=>new Response('credential detail',{status:429,headers:{'retry-after':'0.2'}}))),(e:any)=>e instanceof JevTransportError&&e.code==='HTTP'&&e.status===429&&e.retryAfterMs===200&&!e.message.includes('credential'));
  await assert.rejects(postJevOnce(request,options(async()=>{throw Error('secret');})),(e:any)=>e instanceof JevTransportError&&e.code==='TRANSPORT'&&e.uncertain);
  const interrupted=new ReadableStream<Uint8Array>({start(controller){controller.error(Error('private stream error'));}});
  await assert.rejects(postJevOnce(request,options(async()=>new Response(interrupted))),(e:any)=>e instanceof JevTransportError&&e.code==='TRANSPORT'&&e.uncertain);
});
test('finite transport limits and timeout are required',async()=>{
  await assert.rejects(postJevOnce(request,options(async()=>new Response('{}'),{maxResponseBytes:Number.NaN})),(e:any)=>e instanceof JevTransportError&&e.code==='ROUTE');
  await assert.rejects(postJevOnce(request,{...options(async()=>new Response('{}')),timeoutMs:0}),(e:any)=>e instanceof JevTransportError&&e.code==='ROUTE');
});

test('billing evidence is captured immediately and survives every post-header failure',async()=>{
  const expectedSource='PlusVibe x-pv-cost-rub response header';
  const charged=(error:any,code:string,status:number,cost:number)=>error instanceof JevTransportError&&error.code===code&&error.status===status&&error.observedBilledCostRub===cost&&error.observedBilledCurrency==='RUB'&&error.billedCostProvenance===expectedSource;
  await assert.rejects(postJevOnce(request,options(async()=>new Response('private provider body',{status:503,headers:{'x-pv-cost-rub':'1.25'}}))),(e:any)=>charged(e,'HTTP',503,1.25));
  await assert.rejects(postJevOnce(request,options(async()=>new Response('private malformed body',{headers:{'x-pv-cost-rub':'0.5'}}))),(e:any)=>charged(e,'INVALID_RESPONSE',200,.5));
  await assert.rejects(postJevOnce(request,options(async()=>new Response(new Uint8Array([0xff]),{headers:{'x-pv-cost-rub':'0.6'}}))),(e:any)=>charged(e,'INVALID_RESPONSE',200,.6));
  await assert.rejects(postJevOnce(request,options(async()=>new Response('private oversized body',{headers:{'x-pv-cost-rub':'0.75'}}),{maxResponseBytes:5})),(e:any)=>charged(e,'BODY_LIMIT',200,.75));
  await assert.rejects(postJevOnce(request,options(async()=>new Response(null,{headers:{'x-pv-cost-rub':'0.8'}}))),(e:any)=>charged(e,'INVALID_RESPONSE',200,.8));
  const invalid=await postJevOnce(request,options(async()=>new Response(JSON.stringify({...envelope,model:'wrong'}),{headers:{'x-pv-cost-rub':'0.9'}})));
  assert.throws(()=>validateJevResult(invalid,request),(e:any)=>charged(e,'INVALID_RESPONSE',200,.9));
  const interrupted=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new TextEncoder().encode('{'));controller.error(Error('private stream failure'));}});
  await assert.rejects(postJevOnce(request,options(async()=>new Response(interrupted,{headers:{'x-pv-cost-rub':'2'}}))),(e:any)=>charged(e,'TRANSPORT',200,2)&&e.uncertain);
});

test('billing observations distinguish a missing header, zero, and an invalid header',async()=>{
  const missing=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope))));
  const zero=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope),{headers:{'x-pv-cost-rub':'0'}})));
  const invalid=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope),{headers:{'x-pv-cost-rub':'NaN'}})));
  assert.equal(missing.observedBilledCostRub,undefined);assert.equal(missing.billingHeaderInvalid,undefined);
  assert.equal(zero.observedBilledCostRub,0);assert.equal(zero.billingHeaderInvalid,undefined);
  assert.equal(invalid.observedBilledCostRub,undefined);assert.equal(invalid.billingHeaderInvalid,true);
  assert.throws(()=>validateJevResult(invalid,request),(e:any)=>e instanceof JevTransportError&&e.status===200&&e.billingHeaderInvalid===true&&e.observedBilledCurrency==='RUB'&&e.billedCostProvenance==='PlusVibe x-pv-cost-rub response header');
});

test('serialized transport errors retain safe billing facts without provider secrets or bodies',async()=>{
  const secret='secret-api-key';const privateBody='private response body';
  await assert.rejects(postJevOnce(request,{...options(async()=>new Response(privateBody,{status:503,headers:{'x-pv-cost-rub':'3.5'}})),apiKey:secret}),(e:any)=>{
    const serialized=JSON.stringify(e);
    assert.equal(e.message,'HTTP');assert.equal(e.status,503);assert.equal(e.observedBilledCostRub,3.5);
    assert.ok(!e.message.includes(secret)&&!e.message.includes(privateBody));
    assert.ok(!serialized.includes(secret)&&!serialized.includes(privateBody));
    assert.match(serialized,/"billedCostProvenance":"PlusVibe x-pv-cost-rub response header"/);
    assert.match(serialized,/"observedBilledCostRub":3.5/);
    return true;
  });
});


test('copied and serialized observations retain charged validation evidence',async()=>{
 const observed=await postJevOnce(request,options(async()=>new Response(JSON.stringify(envelope),{headers:{'x-pv-cost-rub':'0.015'}})));
 for(const copy of [{...observed},JSON.parse(JSON.stringify(observed))]){
  copy.returnedModel='wrong';
  assert.throws(()=>validateJevResult(copy,request),(error:unknown)=>error instanceof JevTransportError&&error.status===200&&error.observedBilledCostRub===0.015);
 }
});
