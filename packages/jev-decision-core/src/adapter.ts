import type { DecisionAdapter, DecisionTask, Selection, DecisionRecord } from '../../bounded-decision-core/src/index.ts';
import { postJevOnce, validateJevResult, JevTransportError, type JevRequest, type JevTransportOptions, type JevNormalizedResult } from './jev.ts';
import { toDecisionRecord } from './contract.ts';

export type JevAdapterOptions = { allowExtraAnswers?:boolean; onError?:(error:JevTransportError)=>void; onResult?:(result:JevNormalizedResult)=>void };
export function makeJevAdapter(options:JevTransportOptions,adapterOptions:JevAdapterOptions={}):DecisionAdapter{
 return {async decide(task:DecisionTask,selection:Selection,context):Promise<DecisionRecord>{
  const request:JevRequest={model:selection.model,state:task.state,questions:Object.fromEntries(Object.entries(task.questions).map(([id,q])=>[id,{type:'choice',instructions:q.instructions,criteria:q.criteria}]))};
  let observed:JevNormalizedResult|undefined;
  try{
   observed=await postJevOnce(request,options);
   adapterOptions.onResult?.(observed);
   const answers=observed.answers?Object.fromEntries(Object.entries(observed.answers).filter(([id])=>Object.hasOwn(request.questions,id))):undefined;
   const normalized={...observed,answers};
   if(selection.returned_model_policy==='any_nonempty'&&(typeof normalized.returnedModel!=='string'||!normalized.returnedModel.trim()))throw new JevTransportError('INVALID_RESPONSE',normalized.responseStatus,undefined,{observedBilledCostRub:normalized.observedBilledCostRub,billingHeaderInvalid:normalized.billingHeaderInvalid});
   const forValidation={...normalized,returnedModel:selection.returned_model_policy==='any_nonempty'?selection.model:normalized.returnedModel,
    ...(selection.provider==='plusvibe'?{}:{observedBilledCostRub:undefined,billingHeaderInvalid:undefined})};
   if(!adapterOptions.allowExtraAnswers&&observed.answers&&Object.keys(observed.answers).length!==Object.keys(request.questions).length)throw new JevTransportError('INVALID_RESPONSE',observed.responseStatus,undefined,{observedBilledCostRub:observed.observedBilledCostRub,billingHeaderInvalid:observed.billingHeaderInvalid});
   validateJevResult(forValidation,request);
   const mapped=toDecisionRecord(normalized,request,{provider:'plusvibe',...context});mapped.provider=selection.provider;
   if(selection.provider!=='plusvibe'){mapped.billing=null;mapped.billing_state='unknown';}
   return mapped as DecisionRecord;
  }catch(error){
   const failure=error instanceof JevTransportError?error:new JevTransportError('INVALID_RESPONSE');
   adapterOptions.onError?.(failure);
   const mapped=toDecisionRecord(failure,request,{provider:'plusvibe',...context});mapped.provider=selection.provider;
   if(observed?.estimatedCostRub!==undefined)mapped.estimate={amount:observed.estimatedCostRub,currency:'RUB',source:null};
   if(selection.provider!=='plusvibe'){mapped.billing=null;mapped.billing_state='unknown';}
   return mapped as DecisionRecord;
  }
 }};
}
