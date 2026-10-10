const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createOutbox, createAccountStorage, deletePrivateData, PRIVATE_COLLECTIONS} = require('../js/sync.js');
const {create: stopwatch} = require('../js/rest-stopwatch.js');
class Storage {
 constructor(){this.data=new Map();} get length(){return this.data.size;} key(i){return [...this.data.keys()][i];}
 getItem(k){return this.data.get(k)??null;} setItem(k,v){this.data.set(k,String(v));} removeItem(k){this.data.delete(k);}
}
const tick = () => new Promise(r=>setImmediate(r));
test('offline writes survive restart, retry one stable document after lost acknowledgement',async()=>{
 const storage=new Storage(),server=new Map();let online=false,fail=true,calls=0;
 const options={storage,currentUid:()=> 'alice',online:()=>online,send:async(uid,op)=>{calls++;server.set(uid+'/'+op.id,op.data);if(fail)throw Error('ack lost');}};
 const first=createOutbox(options);first.enqueue('alice','records','set-1',{weight:80,reps:5});assert.equal(calls,0);
 const restarted=createOutbox(options);online=true;await restarted.flush();assert.equal(Object.keys(restarted.read('alice').ops).length,1);
 fail=false;await restarted.flush();assert.equal(server.size,1);assert.equal(calls,2);assert.equal(Object.keys(restarted.read('alice').ops).length,0);
});
test('account isolation, sign-out and reconnect never dispatch another account queue',async()=>{
 const storage=new Storage(),sent=[];let uid='alice',online=false;
 const box=createOutbox({storage,currentUid:()=>uid,online:()=>online,send:async(u,op)=>sent.push(u)});
 box.enqueue('alice','records','a',{reps:1});uid='bob';box.enqueue('bob','records','b',{reps:2});online=true;
 await box.flush('alice');await box.flush('bob');assert.deepEqual(sent,['bob']);uid=null;await box.flush('alice');assert.equal(sent.length,1);
 uid='alice';await box.flush();assert.deepEqual(sent,['bob','alice']);
});
test('deletion replaces unsent creation and tombstones filter stale server snapshots',async()=>{
 const storage=new Storage(),sent=[];let online=false;
 const box=createOutbox({storage,currentUid:()=> 'a',online:()=>online,send:async(u,op)=>sent.push(op)});
 box.enqueue('a','records','x',{reps:5});box.enqueue('a','records','x',null);online=true;await box.flush();
 assert.equal(sent.length,1);assert.equal(sent[0].data,null);assert.deepEqual(box.overlay('a','records',[{id:'x',data:{reps:5}}]),[]);
});
test('in-flight acknowledgement cannot erase a newer delete',async()=>{
 let release;const storage=new Storage(),sent=[];
 const box=createOutbox({storage,currentUid:()=> 'a',send:async(u,op)=>{sent.push(op);if(sent.length===1)await new Promise(r=>release=r);}});
 box.enqueue('a','records','x',{reps:5});box.enqueue('a','records','x',null);release();await tick();await box.flush();
 assert.equal(sent.length,2);assert.equal(sent[1].data,null);assert.equal(Object.keys(box.read('a').ops).length,0);
});
test('merge updates preserve fields of a pending full creation',()=>{
 const box=createOutbox({storage:new Storage(),currentUid:()=>null,send:async()=>{}});
 box.enqueue('a','accessoryRecords','x',{exercise:'old',reps:10,weight:20});box.enqueue('a','accessoryRecords','x',{exercise:'new'},{merge:true});
 assert.deepEqual(box.read('a').ops['accessoryRecords/x'].data,{exercise:'new',reps:10,weight:20});
});
test('quota failure rejects before dispatch or a saved result',()=>{
 let calls=0;const storage=new Storage();storage.setItem=()=>{throw Error('quota');};
 const box=createOutbox({storage,currentUid:()=> 'a',send:async()=>calls++});assert.throws(()=>box.enqueue('a','records','x',{}),/quota/);assert.equal(calls,0);
});
test('legacy logged-in caches are not claimed by a guest or another user',()=>{
 const storage=new Storage();storage.setItem('mf_was_logged_in','1');storage.setItem('mf_cached_email','alice@example.test');storage.setItem('mf_records_v1','{"private":true}');
 const a=createAccountStorage(storage);a.select(null);assert.equal(storage.getItem(a.key('mf_records_v1')),null);
 a.select('bob','bob@example.test');assert.equal(storage.getItem(a.key('mf_records_v1')),null);
 a.select('alice','alice@example.test');assert.equal(storage.getItem(a.key('mf_records_v1')),'{"private":true}');
 storage.setItem(a.key('mf_records_v1'),'alice');a.select(null);assert.equal(storage.getItem(a.key('mf_records_v1')),null);
});
test('private account cleanup preserves guest and public caches',()=>{
 const storage=new Storage(),a=createAccountStorage(storage);a.select('a');storage.setItem(a.key('mf_records_v1'),'a');storage.setItem('mf_dex_posts_v1','public');a.select('b');storage.setItem(a.key('mf_records_v1'),'b');a.clear('a');assert.equal(storage.getItem(a.key('mf_records_v1')),'b');assert.equal(storage.getItem('mf_dex_posts_v1'),'public');
});
function fakeDb(failAt=Infinity){
 const store=new Map();let commits=0,rootDeleted=false;const batchSizes=[];
 for(const name of PRIVATE_COLLECTIONS)store.set('alice/'+name,Array.from({length:name==='records'?901:2},(_,i)=>({id:String(i),ref:{path:'alice/'+name,id:String(i)}})));
 store.set('bob/records',[{id:'keep'}]);store.set('dexPosts',[{id:'public'}]);
 const db={collection:name=>{assert.equal(name,'users');return {doc:uid=>({delete:async()=>{rootDeleted=true;},collection:col=>({limit:n=>({get:async opts=>{assert.equal(opts.source,'server');return {docs:(store.get(uid+'/'+col)||[]).slice(0,n)};}})})})};},
 batch:()=>{const refs=[];return {delete:r=>refs.push(r),commit:async()=>{commits++;if(commits===failAt)throw Error('network');batchSizes.push(refs.length);for(const r of refs)store.set(r.path,store.get(r.path).filter(d=>d.id!==r.id));}}}};
 return {db,store,batchSizes,get rootDeleted(){return rootDeleted;}};
}
test('account deletion pages over 500 documents, covers every private collection and preserves others',async()=>{
 const f=fakeDb();await deletePrivateData(f.db,'alice');assert.ok(f.rootDeleted);assert.ok(f.batchSizes.every(n=>n<=400));for(const name of PRIVATE_COLLECTIONS)assert.equal(f.store.get('alice/'+name).length,0,name);assert.equal(f.store.get('bob/records').length,1);assert.equal(f.store.get('dexPosts').length,1);
});
test('partial deletion never deletes auth/root prematurely and rerun completes remaining data',async()=>{
 const f=fakeDb(2);await assert.rejects(deletePrivateData(f.db,'alice'),/network/);assert.equal(f.rootDeleted,false);assert.equal(f.store.get('alice/records').length,501);await deletePrivateData(f.db,'alice');assert.ok(f.rootDeleted);assert.equal(f.store.get('alice/records').length,0);
});
test('deletion stops when account changes',async()=>{
 const f=fakeDb();await assert.rejects(deletePrivateData(f.db,'alice',()=>{throw Error('account changed');}));assert.equal(f.store.get('alice/records').length,901);assert.equal(f.rootDeleted,false);
});
test('persisted deletion blocks writes after restart',async()=>{
 const storage=new Storage(),opts={storage,currentUid:()=> 'a',send:async()=>{}};const box=createOutbox(opts);await box.freeze('a');assert.throws(()=>createOutbox(opts).enqueue('a','records','x',{}),/탈퇴/);
});
test('running and paused stopwatch restore timestamp state across new instances',()=>{
 const storage=new Storage();let now=1000;const opts={storage,key:'timer',now:()=>now};const first=stopwatch(opts);first.reset();now=61000;assert.equal(stopwatch(opts).restore().startedAt,1000);const second=stopwatch(opts);second.restore();assert.equal(second.elapsed(),60000);second.togglePause();now=181000;const third=stopwatch(opts);assert.equal(third.restore().pausedAt,61000);assert.equal(third.elapsed(),60000);third.togglePause();now=191000;assert.equal(third.elapsed(),70000);assert.equal(third.restore().pausedTotalMs,120000);
});
test('30 minute expiry includes background elapsed and excludes paused time',()=>{
 const storage=new Storage();let now=1000;const opts={storage,key:'timer',now:()=>now};const t=stopwatch(opts);t.reset();now+=1800000;assert.ok(t.expired());assert.equal(stopwatch(opts).restore().active,false);assert.equal(storage.getItem('timer'),null);
 t.reset();now+=60000;t.togglePause();now+=7200000;const r=stopwatch(opts);assert.equal(r.restore().active,true);assert.equal(r.elapsed(),60000);
});
test('reset and manual stop remove saved stopwatch state; corrupt data does not run',()=>{
 const storage=new Storage();let now=1000;const t=stopwatch({storage,key:'timer',now:()=>now});t.reset();now+=5000;t.togglePause();t.reset();assert.equal(t.elapsed(),0);t.stop();assert.equal(storage.getItem('timer'),null);storage.setItem('timer','{bad');assert.equal(t.restore().active,false);
});
test('exercise deletion cancels pending sets and hides stale history after acknowledgement',async()=>{
 const sent=[];const box=createOutbox({storage:new Storage(),currentUid:()=>null,send:async(_,op)=>sent.push(op)});
 box.enqueue('a','accessoryRecords','x',{exercise:'curl',reps:5});box.enqueue('a','accessoryRecords','y',{exercise:'press',reps:8});
 box.enqueue('a','accessoryRecords','query-delete',null,{matchExercise:'curl'});
 assert.equal(box.read('a').ops['accessoryRecords/x'],undefined);
 assert.deepEqual(box.overlay('a','accessoryRecords',[{id:'old',data:{exercise:'curl'}},{id:'z',data:{exercise:'press'}}]).map(d=>d.id).sort(),['y','z']);
});
test('exercise rename keeps pending set fields and updates stale server documents in overlay',()=>{
 const box=createOutbox({storage:new Storage(),currentUid:()=>null,send:async()=>{}});
 box.enqueue('a','accessoryRecords','x',{exercise:'old',weight:20,reps:10});box.enqueue('a','accessoryRecords','query-rename',{exercise:'new'},{matchExercise:'old'});
 const docs=box.overlay('a','accessoryRecords',[{id:'server',data:{exercise:'old',reps:2}}]);assert.ok(docs.every(d=>d.data.exercise==='new'));assert.equal(docs.find(d=>d.id==='x').data.reps,10);
});
