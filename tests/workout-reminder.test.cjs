const {test}=require('node:test');const assert=require('node:assert/strict');
const {create,hasRecord}=require('../js/workout-reminder.js');
function fixture(){
 const memory=new Map(),requests=[];const storage={getItem:k=>memory.get(k)??null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
 const f={uid:'alice',value:{ready:true,hasRecord:false,hasLocalRecord:false,basis:'2026-10-27T12:59:00Z'},pending:false,requests,memory,syncs:0};
 const client=create({auth:{get currentUser(){return f.uid?{uid:f.uid,getIdToken:async()=> 'auth-'+f.uid}:null;}},storage,
  config:{reminderApiUrl:'https://reminders.test'},getWorker:async()=>{},online:()=>true,now:()=>Date.parse('2026-10-27T13:00:00Z'),
  readActivity:()=>f.value,syncRecords:async()=>{f.syncs++;return true;},pending:()=>f.pending,
  fetchFn:async(url,options)=>{requests.push({url,...options,body:options.body?JSON.parse(options.body):undefined});return {ok:true,json:async()=>({ok:true})};}});
 return {...f,client,get uid(){return f.uid;},set uid(v){f.uid=v;},get value(){return f.value;},set value(v){f.value=v;},get pending(){return f.pending;},set pending(v){f.pending=v;},get syncs(){return f.syncs;}};
}
test('real records include lifts, zero-weight bodyweight sets and completed routines, not calendar/plans',()=>{
 const day='2026-10-27';
 assert.equal(hasRecord([{bench:[{date:'26.10.27',reps:1,weight:100}]}],day),true);
 assert.equal(hasRecord([{pushups:[{date:'26.10.27',reps:10,weight:0}]}],day),true);
 assert.equal(hasRecord([{routines:[{date:'26.10.27',totalSets:3,totalReps:30}]}],day),true);
 for(const row of [{date:'26.10.26',reps:5},{date:'26.10.27',muscles:['가슴']},{date:'26.10.27',reps:0},{date:'26.10.27',reps:5,deleted:true}])assert.equal(hasRecord([{x:[row]}],day),false);
});
test('activity payload contains only date, booleans, device identifier and snapshot basis; unchanged state is deduped',async()=>{
 const f=fixture();await f.client.publish();await f.client.publish({refresh:true});
 assert.equal(f.requests.length,1);assert.equal(f.syncs,0);
 assert.deepEqual(Object.keys(f.requests[0].body).sort(),['basis','day','deviceId','hasLocalRecord','hasRecord']);
 assert.equal(f.requests[0].headers.Authorization,'Bearer auth-alice');assert.ok(!JSON.stringify(f.requests).includes('weight'));
});
test('not loaded, pending server writes, guests and frozen accounts do not publish false absence',async()=>{
 const f=fixture();f.value={ready:false};await f.client.publish();
 f.value={ready:true,hasRecord:false};f.pending=true;await f.client.publish();f.pending=false;
 f.uid=null;await f.client.publish();f.uid='alice';f.client.freeze();await f.client.publish();assert.equal(f.requests.length,0);
});
test('first set and last-set deletion refresh existing delta sync before publishing changed status',async()=>{
 const f=fixture();await f.client.publish();f.value={...f.value,hasRecord:true};await f.client.publish({refresh:true});
 f.value={...f.value,hasRecord:false};await f.client.publish({refresh:true});
 assert.deepEqual(f.requests.map(r=>r.body.hasRecord),[false,true,false]);assert.equal(f.syncs,2);
});
test('local routine presence is independent and cannot be dropped by boolean dedupe',async()=>{
 const f=fixture();await f.client.publish();f.value={...f.value,hasLocalRecord:true};await f.client.publish({refresh:true});
 assert.deepEqual(f.requests.map(r=>r.body.hasLocalRecord),[false,true]);
});
test('logout freezes activity but still permits intentional device removal',async()=>{
 const f=fixture();f.client.freeze();await f.client.remove('alice','device');await f.client.publish();
 assert.equal(f.requests.length,1);assert.equal(f.requests[0].url,'https://reminders.test/device');assert.equal(f.requests[0].method,'DELETE');
});
test('account erasure deletes minimal metadata and clears scoped acknowledgement',async()=>{
 const f=fixture();await f.client.publish();await f.client.forget();await f.client.publish();
 assert.equal(f.requests.at(-1).url,'https://reminders.test/account');assert.equal(f.memory.has('mf_account_v2:alice:reminder_activity_v1'),false);assert.equal(f.requests.length,2);
});
