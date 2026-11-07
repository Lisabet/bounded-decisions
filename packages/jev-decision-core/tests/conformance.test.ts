import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {postJevOnce,JevTransportError} from '../src/jev.ts';
import {acceptDecisionRecord,toDecisionRecord} from '../src/contract.ts';
const fixtures=JSON.parse(readFileSync(new URL('../contract/fixtures.json',import.meta.url),'utf8'));
for(const item of fixtures.cases)test('shared '+item.id,async()=>{
 const fetchImpl=async()=>{
  if(item.transport_error)throw new Error('private network detail');
  return new Response(typeof item.response.body==='string'?item.response.body:JSON.stringify(item.response.body),{status:item.response.status,headers:item.response.headers});
 };
 let actual;
 try{
  if(item.transport_error==='timeout')throw new JevTransportError('TIMEOUT');
  const result=await postJevOnce(item.request,{url:new URL('https://example.invalid/v1/decisions'),apiKey:'synthetic-key',timeoutMs:1000,fetchImpl:fetchImpl as typeof fetch});
  actual=acceptDecisionRecord(result,item.request,{provider:'plusvibe',receiptId:'fixture-attempt'});
 }catch(error){assert.ok(error instanceof JevTransportError);actual=toDecisionRecord(error,item.request,{provider:'plusvibe',receiptId:'fixture-attempt'});}
 assert.deepEqual(actual,item.expected);
});


test('PlusVibe billing mapping requires its provider identity',()=>{
 assert.throws(()=>toDecisionRecord(new JevTransportError('TIMEOUT'),fixtures.cases[0].request,{provider:'other'}),TypeError);
});
