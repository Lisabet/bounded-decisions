/** Canonical operation record. Persist it under the caller's durable attempt identity. */
import {JevTransportError,validateJevResult} from './jev.ts';
import type {JevNormalizedResult,JevRequest} from './jev.ts';
export const CONTRACT_VERSION='bounded-decisions/1';
type Money={amount:number;currency:string;source:string|null};
export type DecisionRecord={
 contract_version:string;provider:string;requested_model:string;returned_model:string|null;
 status:'ok'|'error'|'pending';answers:Record<string,unknown>;usage:Record<string,number>|null;
 billing:Money|null;billing_state:'observed'|'unknown'|'invalid';estimate:Money|null;
 receipt:{id:string|null;reused:boolean};uncertain:boolean;error:{code:string;http_status:number|null}|null;
};
/** Map an accepted observation or safe error. Call validateJevResult before accepting a transport result. */
export function toDecisionRecord(value:JevNormalizedResult|JevTransportError,request:JevRequest,
 context:{provider:string;receiptId?:string;reused?:boolean;estimateSource?:string}):DecisionRecord{
 if(context.provider!=='plusvibe')throw new TypeError('unsupported_contract_provider');
 const failed=value instanceof JevTransportError;
 const result=failed?undefined:value as JevNormalizedResult;
 const failure=failed?value as JevTransportError:undefined;
 const amount=value.observedBilledCostRub;
 const billing=amount===undefined?null:{amount,currency:'RUB',source:'PlusVibe x-pv-cost-rub response header'};
 const answers:Record<string,unknown>={};
 if(result?.answers)for(const [id,raw] of Object.entries(result.answers)){
  const detail=raw as Record<string,unknown>;
  Object.defineProperty(answers,id,{enumerable:true,configurable:true,writable:true,value:{type:'choice',...Object.fromEntries(['choice','probabilities','confidence'].filter(k=>Object.hasOwn(detail,k)).map(k=>[k,detail[k]]))}});
 }
 return {contract_version:CONTRACT_VERSION,provider:context.provider,requested_model:request.model,
 returned_model:result?.returnedModel??null,status:failure?(failure.uncertain?'pending':'error'):'ok',answers,
 usage:result?.usage??null,billing,billing_state:value.billingHeaderInvalid?'invalid':(billing?'observed':'unknown'),
 estimate:result?.estimatedCostRub===undefined?null:{amount:result.estimatedCostRub,currency:'RUB',source:context.estimateSource??null},
 receipt:{id:context.receiptId??null,reused:context.reused??false},uncertain:failure?.uncertain??false,
 error:failure?{code:({ROUTE:'route',INPUT_LIMIT:'input_limit',BODY_LIMIT:'body_limit',HTTP:'http',INVALID_RESPONSE:'invalid_response',TIMEOUT:'timeout',TRANSPORT:'transport'} as const)[failure.code],http_status:failure.status??null}:null};
}
/** Strict common acceptance plus mapping, preserving charged validation errors. */
export function acceptDecisionRecord(value:JevNormalizedResult,request:JevRequest,context:{provider:string;receiptId?:string;reused?:boolean;estimateSource?:string}):DecisionRecord{
 validateJevResult(value,request);
 return toDecisionRecord(value,request,context);
}
