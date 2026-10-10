const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../js/last-workout.js');
const {createOutbox,createAccountStorage}=require('../js/sync.js');
class Storage{
 constructor(){this.data=new Map();}get length(){return this.data.size;}key(i){return [...this.data.keys()][i];}
 getItem(k){return this.data.get(k)??null;}setItem(k,v){this.data.set(k,String(v));}removeItem(k){this.data.delete(k);}
}
const docs=entries=>Object.entries(entries).map(([id,data])=>({id,data}));
const fixtures={'2026-9-30':{muscles:['하체']},'2026-8-20':{muscles:['하체','가슴']},'2025-12-31':{muscles:['등']},'2026-10-11':{muscles:['어깨'],confirmed:false}};
const NOW=Date.parse('2026-10-10T02:00:00Z');
function database(initial={}){
 const store=new Map(Object.entries(initial)),reads=[],writes=[];let offline=false,tail=Promise.resolve(),failCommit=false;
 const snap=(r)=>({exists:store.has(r.path),data:()=>structuredClone(store.get(r.path))});
 const ref=path=>({path,collection:n=>collection(path+'/'+n),get:async opts=>{reads.push({path,source:opts?.source});if(offline)throw Error('offline');return snap({path});}});
 const collection=path=>({doc:id=>ref(path+'/'+id),get:async opts=>{reads.push({path,source:opts?.source});if(offline)throw Error('offline');return {docs:[...store].filter(([p])=>p.startsWith(path+'/')&&p.split('/').length===path.split('/').length+1).map(([p,d])=>({id:p.split('/').at(-1),data:()=>structuredClone(d)}))};}});
 const db={collection,runTransaction:fn=>{
   const work=tail.catch(()=>{}).then(async()=>{
    if(offline)throw Error('offline');const staged=[];
    const result=await fn({get:r=>r.get({source:'server'}),set:(r,d)=>staged.push([r.path,structuredClone(d)]),delete:r=>staged.push([r.path,null])});
    if(failCommit){failCommit=false;throw Error('commit lost');}
    for(const [p,d] of staged){writes.push(p);if(d===null)store.delete(p);else store.set(p,d);}
    return result;
   });tail=work;return work;
 }};
 return {db,store,reads,writes,setOffline:v=>offline=v,failNext:()=>failCommit=true};
}
function service(env,storage=new Storage(),getUid=()=> 'alice'){
 return M.createService({db:env.db,storage,currentUid:getUid,now:()=>NOW});
}
const summaryPath='users/alice/meta/'+M.DOCUMENT;
test('Korean dates cross month/year boundaries; future entries become eligible locally',()=>{
 const value=M.build(docs(fixtures),'2026-10-10');
 assert.equal(value.latest['하체'],'2026-09-30');assert.equal(M.elapsed(value.latest['하체'],'2026-10-10'),10);
 assert.equal(M.elapsed('2025-12-31','2026-01-01'),1);assert.equal(value.latest['어깨'],undefined);
 assert.equal(M.dates(value,'2026-10-11')['어깨'],'2026-10-11');
 assert.equal(M.today(Date.parse('2026-10-09T15:00:00Z')),'2026-10-10');
 assert.equal(M.date('2026-2-30'),null);
 const leap=M.build(docs({'2024-2-29':{muscles:['등']}}),'2024-03-01');assert.equal(M.elapsed(leap.latest['등'],'2024-03-01'),1);
});
test('deleting/changing the latest tag returns to the previous date without a server history read',()=>{
 let value=M.build(docs(fixtures),'2026-10-10');value=M.apply(value,'2026-9-30',{muscles:['어깨']},'2026-10-10');
 assert.equal(value.latest['하체'],'2026-08-20');assert.equal(value.latest['어깨'],'2026-09-30');
 value=M.apply(value,'2026-8-20',null,'2026-10-10');assert.equal(value.latest['하체'],undefined);
 assert.equal(value.latest['등'],'2025-12-31');
});
test('compact masks cover decades and remain far below the Firestore document limit',()=>{
 const entries=[];for(let year=2000;year<2100;year++)for(let day=0;day<365;day++)entries.push({id:new Date(Date.UTC(year,0,1)+day*86400000).toISOString().slice(0,10),data:{muscles:M.PARTS}});
 const value=M.build(entries,'2099-12-31');assert.ok(M.valid(value));assert.ok(JSON.stringify(value).length<100000);
});
test('initial migration reads all calendar exactly once; subsequent app loads read one summary only',async()=>{
 const initial=Object.fromEntries(Object.entries(fixtures).map(([id,d])=>['users/alice/calendar/'+id,d]));
 const env=database(initial),storage=new Storage(),first=service(env,storage);
 await Promise.all([first.load('alice'),first.load('alice')]);assert.ok(env.store.has(summaryPath));
 assert.equal(env.reads.filter(r=>r.path==='users/alice/calendar').length,1);
 assert.equal(first.view('alice').dates['하체'],'2026-09-30');
 const before=env.reads.length,restarted=service(env,storage);await restarted.load('alice');await restarted.load('alice');
 assert.equal(env.reads.length-before,1);assert.equal(env.reads.filter(r=>r.path==='users/alice/calendar').length,1);
 assert.equal(env.reads.at(-1).source,'server');
});
test('calendar and summary commit atomically; failures can retry and deletion is idempotent',async()=>{
 const env=database({[summaryPath]:M.build(docs(fixtures),'2026-10-10')}),s=service(env);
 await s.load('alice');env.failNext();
 await assert.rejects(s.send('alice',{id:'2026-10-10',data:{muscles:['하체']}}));
 assert.equal(env.store.has('users/alice/calendar/2026-10-10'),false);
 assert.equal(env.store.get(summaryPath).latest['하체'],'2026-09-30');
 await s.send('alice',{id:'2026-10-10',data:{muscles:['하체']}});
 assert.equal(env.store.get(summaryPath).latest['하체'],'2026-10-10');
 await s.send('alice',{id:'2026-10-10',data:null});await s.send('alice',{id:'2026-10-10',data:null});
 assert.equal(env.store.get(summaryPath).latest['하체'],'2026-09-30');
 assert.equal(env.reads.filter(r=>r.path==='users/alice/calendar').length,0);
});
test('offline outbox survives restart, previews removal and commits both documents on reconnect',async()=>{
 const initial=M.build(docs(fixtures),'2026-10-10'),env=database({[summaryPath]:initial}),storage=new Storage();
 const s=service(env,storage);await s.load('alice');env.setOffline(true);let online=false;
 const create=svc=>createOutbox({storage,currentUid:()=> 'alice',online:()=>online,send:(uid,op)=>svc.send(uid,op)});
 let box=create(s);box.enqueue('alice','calendar','2026-9-30',null);
 assert.equal(s.view('alice',box.read('alice').ops).dates['하체'],'2026-08-20');
 const restarted=service(env,storage);box=create(restarted);
 assert.equal(restarted.view('alice',box.read('alice').ops).dates['하체'],'2026-08-20');
 env.setOffline(false);online=true;await box.flush();
 assert.equal(Object.keys(box.read('alice').ops).length,0);assert.equal(env.store.get(summaryPath).latest['하체'],'2026-08-20');
});
test('unknown offline account is not initialized from partial device data',async()=>{
 const env=database(),s=service(env);env.setOffline(true);await assert.rejects(s.load('alice'));
 assert.equal(env.store.has(summaryPath),false);assert.equal(s.view('alice').known,false);
 env.setOffline(false);await s.load('alice');assert.equal(s.view('alice').known,true);
});
test('concurrent device mutations preserve both dates; account caches and deletion stay isolated',async()=>{
 const env=database({[summaryPath]:M.empty()}),storage=new Storage(),a=service(env,storage),b=service(env,new Storage());
 await Promise.all([a.load('alice'),b.load('alice')]);
 await Promise.all([a.send('alice',{id:'2026-10-9',data:{muscles:['가슴']}}),b.send('alice',{id:'2026-10-8',data:{muscles:['등']}})]);
 assert.deepEqual(env.store.get(summaryPath).latest,{'가슴':'2026-10-09','등':'2026-10-08'});
 const bob=service(env,storage,()=> 'bob');assert.equal(bob.view('bob').known,false);
 await assert.rejects(bob.send('alice',{id:'2026-10-10',data:null}));
 const account=createAccountStorage(storage);storage.setItem('mf_account_v2:bob:last_workout_dates_v1','keep');account.clear('alice');
 assert.equal(storage.getItem('mf_account_v2:alice:last_workout_dates_v1'),null);assert.equal(storage.getItem('mf_account_v2:bob:last_workout_dates_v1'),'keep');
});
test('pending replacement cancels older deletion in local summary preview',()=>{
 const value=M.build(docs(fixtures),'2026-10-10');
 const result=M.overlay(value,{a:{collection:'calendar',id:'2026-9-30',data:{muscles:['하체','등']}},b:{collection:'records',id:'ignore',data:null}},'2026-10-10');
 assert.equal(result['하체'],'2026-09-30');assert.equal(result['등'],'2026-09-30');
});
test('account deletion interrupts historical initialization before it can recreate private metadata',async()=>{
 const env=database({'users/alice/calendar/2026-9-30':{muscles:['하체']}}),storage=new Storage();let deleting=false,release,entered;
 const started=new Promise(r=>entered=r),gate=new Promise(r=>release=r),original=env.db.collection;
 env.db.collection=name=>{
  const users=original(name);
  return {doc:uid=>{
   const user=users.doc(uid);
   return {collection:collection=>{
    const ref=user.collection(collection);
    return collection==='calendar'?{...ref,get:async options=>{entered();await gate;return ref.get(options);}}:ref;
   }};
  }};
 };
 const s=M.createService({db:env.db,storage,currentUid:()=> 'alice',isDeleting:()=>deleting,now:()=>NOW});
 const work=s.load('alice'),rejection=assert.rejects(work);await started;deleting=true;release();
 await rejection;await s.idle('alice');assert.equal(env.store.has(summaryPath),false);
});
test('another tab updates the shared local summary without additional server reads',async()=>{
 const env=database({[summaryPath]:M.empty()}),storage=new Storage(),first=service(env,storage),second=service(env,storage);
 await Promise.all([first.load('alice'),second.load('alice')]);
 await second.send('alice',{id:'2026-10-10',data:{muscles:['하체']}});
 const reads=env.reads.length;
 assert.equal(first.view('alice').dates['하체'],'2026-10-10');assert.equal(env.reads.length,reads);
});
