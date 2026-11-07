/** Run with Node24.16+ from this checkout; all observations are synthetic. */
import {executeTask} from '../../bounded-decision-core/src/index.ts';
import type {DecisionTask,DecisionAdapter} from '../../bounded-decision-core/src/index.ts';
const task:DecisionTask={task_version:'bounded-task/1',task_id:'synthetic-support-1',rules_version:'support/1',state:{message:'Move delivery to Friday'},questions:{route:{type:'choice',instructions:'Choose the matching department.',criteria:{delivery:'Delivery scheduling',payment:'Payment and refunds',review:'Human review'},abstain_choice:'review'}}};
const adapter:DecisionAdapter={decide:(_task,selection,context)=>({contract_version:'bounded-decisions/1',provider:selection.provider,requested_model:selection.model,returned_model:selection.model,status:'ok',answers:{route:{type:'choice',choice:'delivery'}},usage:null,billing:{amount:0,currency:'USD',source:'Synthetic observation'},billing_state:'observed',estimate:null,receipt:{id:context.receiptId??null,reused:false},uncertain:false,error:null})};
for(const provider of ['fixture-a','fixture-b']){
 const outcome=await executeTask(task,{provider,model:'synthetic/model'},new Map([[provider,adapter]]),{expected_choices:{route:'delivery'}},{receiptId:'offline-attempt'});
 if(outcome.evaluation.status!=='accepted'||!outcome.evaluation.quality?.matched)throw Error('offline example failed');
 console.log(provider,outcome.record.answers.route,outcome.evaluation.status);
}
