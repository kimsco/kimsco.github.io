const {test}=require('node:test');const assert=require('node:assert/strict');
const {createService}=require('../js/record-changes.js');
function fixture(){
 const store=new Map(),calls=[];let queue=Promise.resolve(),lostAck=false,denied=false;
 const snap=(path,data)=>({id:path.split('/').at(-1),exists:data!==undefined,ref:ref(path),data:()=>structuredClone(data)});
 function ref(path){return {path,collection:name=>query(path+'/'+name),get:async()=>{calls.push(['get',path]);return snap(path,store.get(path));},set:async data=>store.set(path,structuredClone(data)),delete:async()=>store.delete(path)};}
 function query(path,filters=[],max=Infinity,after){return {doc:id=>ref(path+'/'+id),where:(f,o,v)=>query(path,[...filters,[f,o,v]],max,after),orderBy:()=>query(path,filters,max,after),limit:n=>query(path,filters,n,after),startAfter:doc=>query(path,filters,max,{version:doc.data().version,id:doc.id}),get:async()=>{
  calls.push(['query',path]);let rows=[...store].filter(([key,data])=>key.startsWith(path+'/')&&key.split('/').length===path.split('/').length+1&&filters.every(([f,o,v])=>o==='>'?data[f]>v:o==='<='?data[f]<=v:data[f]===v));
  rows.sort((a,b)=>(a[1].version||0)-(b[1].version||0)||a[0].localeCompare(b[0]));
  if(after)rows=rows.filter(([key,data])=>data.version>after.version || (data.version===after.version && key.split('/').at(-1)>after.id));
  const docs=rows.slice(0,max).map(([key,data])=>snap(key,data));return {docs,empty:!docs.length};
 }};}
 const db={collection:name=>query(name),runTransaction:fn=>{
  const task=queue.catch(()=>{}).then(async()=>{
   const ops=[];const value=await fn({get:r=>r.get(),set:(r,data)=>ops.push(['set',r.path,data]),delete:r=>ops.push(['delete',r.path])});
   if(denied && ops.some(op=>op[1].includes('/recordChanges/'))){const error=Error('denied');error.code='permission-denied';throw error;}
   assert.ok(ops.length<=500);calls.push(['transaction',ops.length]);
   for(const [kind,path,data] of ops)kind==='delete'?store.delete(path):store.set(path,structuredClone(data));
   if(lostAck){lostAck=false;throw Error('Lost acknowledgement');}return value;
  });queue=task;return task;
 }};
 return {db,store,calls,setLostAck:()=>lostAck=true,setDenied:()=>denied=true};
}
function storage(){const map=new Map();return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v)};}
function client(f,id='alice'){let owner=id,deleting=false,time=1000;const s=storage();const service=createService({db:f.db,storage:s,currentUid:()=>owner,isDeleting:()=>deleting,now:()=>time,checkMs:0});return {service,storage:s,owner:v=>owner=v,deleting:()=>deleting=true,time:v=>time=v};}
const op=(id,seq,collection='records',data={date:'26.10.13',lift:'bench',weight:60,reps:5})=>({id,collection,data,merge:false,clientId:'device-a',clientSeq:seq});
test('unchanged warm restart reads only metadata; changes and deletes use the feed',async()=>{
 const f=fixture(),a=client(f);let data=new Map(),bootstraps=0;
 const options={hasLocal:()=>true,bootstrap:async()=>bootstraps++,apply:async changes=>changes.forEach(x=>x.deleted?data.delete(x.id):data.set(x.id,x.data))};
 await a.service.sync('alice',options);assert.equal(bootstraps,1);
 const b=createService({db:f.db,storage:a.storage,currentUid:()=> 'alice',checkMs:0,now:()=>1001});f.calls.length=0;
 assert.equal((await b.sync('alice',options)).mode,'unchanged');assert.deepEqual(f.calls,[['get','users/alice/meta/recordSync']]);
 await a.service.write('alice',op('one',1));await b.sync('alice',options);assert.equal(data.get('one').weight,60);
 await a.service.write('alice',op('one',2,'records',null));await b.sync('alice',options);assert.equal(data.has('one'),false);assert.equal(bootstraps,1);
});
test('lost acknowledgement followed by remote delete never resurrects a record on retry',async()=>{
 const f=fixture(),a=client(f),b=client(f);await a.service.ensure('alice');const create=op('stable',1);
 f.setLostAck();await assert.rejects(a.service.write('alice',create),/Lost/);
 await b.service.write('alice',{...op('stable',1,'records',null),clientId:'device-b'});
 await a.service.write('alice',create);assert.equal(f.store.has('users/alice/records/stable'),false);
 await a.service.write('alice',{...op('stable',2),merge:true});assert.equal(f.store.has('users/alice/records/stable'),false);
 assert.equal(f.store.get('users/alice/meta/recordSync').version,2);
});
test('merge feed stores full current record and simultaneous devices serialize versions',async()=>{
 const f=fixture(),a=client(f),b=client(f);await a.service.ensure('alice');
 await Promise.all([a.service.write('alice',op('a',1)),b.service.write('alice',{...op('b',1),clientId:'device-b'})]);
 await a.service.write('alice',{...op('a',2,'records',{weight:70}),merge:true});
 const events=[...f.store].filter(([path,data])=>path.includes('/recordChanges/')&&!data.protocol).map(([,data])=>data);
 assert.deepEqual(events.map(x=>x.version).sort(),[2,3]);const updated=events.find(x=>x.id==='a');assert.equal(updated.data.reps,5);assert.equal(updated.data.weight,70);
});
test('group deletion paginates tied versions safely and completes durable client receipt',async()=>{
 const f=fixture(),a=client(f);let applied=[];await a.service.sync('alice',{hasLocal:()=>true,bootstrap:async()=>{},apply:async()=>{}});
 const docs=Array.from({length:251},(_,i)=>{const id='r'+i;const path='users/alice/accessoryRecords/'+id;f.store.set(path,{exercise:'Old',weight:60});return {id,ref:f.db.collection('users').doc('alice').collection('accessoryRecords').doc(id)};});
 const mutation={...op('group',1,'accessoryRecords',null),matchExercise:'Old'};
 await a.service.writeGroup('alice',mutation,docs.slice(0,200));await a.service.writeGroup('alice',mutation,docs.slice(200));await a.service.writeGroup('alice',mutation,[],{finish:true});
 await a.service.sync('alice',{hasLocal:()=>true,bootstrap:async()=>assert.fail(),apply:async changes=>applied.push(...changes)});
 assert.equal(applied.length,251);assert.equal(new Set(applied.map(x=>x.id)).size,251);assert.ok(applied.every(x=>x.deleted));assert.equal(f.store.get('users/alice/meta/recordSync').clients['device-a'],1);
});
test('failed persistence does not advance cursor; replay and account/deletion guards are safe',async()=>{
 const f=fixture(),a=client(f);const options={hasLocal:()=>true,bootstrap:async()=>{},apply:async()=>{throw Error('storage full');}};await a.service.sync('alice',options);await a.service.write('alice',op('one',1));
 await assert.rejects(a.service.sync('alice',options),/storage full/);assert.equal(a.service.readCursor('alice').version,0);
 let count=0;await a.service.sync('alice',{...options,apply:async x=>count+=x.length});assert.equal(count,1);assert.equal(a.service.readCursor('alice').version,1);
 a.owner('bob');await assert.rejects(a.service.write('alice',op('two',2)),/Account/);a.owner('alice');a.deleting();await assert.rejects(a.service.sync('alice',options),/deleting/);
});
test('permission denial aborts protocol setup atomically and reports legacy fallback',async()=>{
 const f=fixture(),a=client(f);f.setDenied();assert.equal(await a.service.ensure('alice'),false);assert.equal(f.store.size,0);
 assert.equal(await a.service.write('alice',op('one',1)),false);
 assert.equal((await a.service.sync('alice',{hasLocal:()=>true,bootstrap:async()=>assert.fail(),apply:async()=>assert.fail()})).mode,'legacy');
});
test('remote deletion tombstones filter late historical snapshots and explicit newer creation clears them',async()=>{
 const f=fixture(),a=client(f);a.service.noteApplied('alice',[{collection:'records',id:'one',version:2,deleted:true}]);
 const doc={id:'one',data:()=>({weight:60})};assert.equal(a.service.filterSnapshot('alice','records',{docs:[doc]}).docs.length,0);
 a.service.noteApplied('alice',[{collection:'records',id:'one',version:3,deleted:false}]);assert.equal(a.service.filterSnapshot('alice','records',{docs:[doc]}).docs.length,1);
 assert.equal(a.service.filterSnapshot('alice','profile',{docs:[doc]}).docs.length,1);
});
test('confirmed own writes advance only a contiguous local cursor without rereading own records',async()=>{
 const f=fixture(),s=storage(),commits=[];const a=createService({db:f.db,storage:s,currentUid:()=> 'alice',now:()=>1000,checkMs:0,onCommit:(_,commit)=>commits.push(commit)});
 const options={hasLocal:()=>true,bootstrap:async()=>{},apply:async()=>{}};await a.sync('alice',options);
 await a.write('alice',op('one',1));a.advanceOwn('alice',commits);assert.equal(a.readCursor('alice').version,1);
 const restarted=createService({db:f.db,storage:s,currentUid:()=> 'alice',now:()=>1001,checkMs:0});f.calls.length=0;
 assert.equal((await restarted.sync('alice',options)).mode,'unchanged');assert.deepEqual(f.calls,[['get','users/alice/meta/recordSync']]);
});
test('own cursor never jumps across a version written by another device',async()=>{
 const f=fixture(),s=storage(),commits=[],a=createService({db:f.db,storage:s,currentUid:()=> 'alice',now:()=>1000,checkMs:0,onCommit:(_,commit)=>commits.push(commit)}),b=client(f);
 const options={hasLocal:()=>true,bootstrap:async()=>{},apply:async()=>{}};await a.sync('alice',options);
 await a.write('alice',op('one',1));await b.service.write('alice',{...op('remote',1),clientId:'device-b'});await a.write('alice',op('two',2));
 a.advanceOwn('alice',commits);assert.equal(a.readCursor('alice').version,1);
 const received=[];await a.sync('alice',{...options,apply:async changes=>received.push(...changes)});assert.deepEqual(received.map(x=>x.id).sort(),['remote','two']);assert.equal(a.readCursor('alice').version,3);
});
test('deletion waits for initialization and initialization cannot recreate private protocol documents',async()=>{
 const f=fixture(),a=client(f);const original=f.db.collection;let release;
 f.db.collection=name=>{const collection=original(name),doc=collection.doc;collection.doc=id=>{const parent=doc(id),child=parent.collection;parent.collection=key=>{const nested=child(key),getDoc=nested.doc;nested.doc=field=>{const ref=getDoc(field),get=ref.get;if(key==='meta'&&field==='recordSync')ref.get=async()=>{await new Promise(r=>release=r);return get();};return ref;};return nested;};return parent;};return collection;};
 const loading=a.service.sync('alice',{hasLocal:()=>true,bootstrap:async()=>assert.fail(),apply:async()=>assert.fail()});await new Promise(r=>setImmediate(r));a.deleting();const idle=a.service.idle('alice');release();await assert.rejects(loading,/deleting/);await idle;assert.equal(f.store.size,0);
});
