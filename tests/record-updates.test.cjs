const {test}=require('node:test');const assert=require('node:assert/strict');
const {create}=require('../js/record-updates.js');
function fixture(){
 let uid='a',clock=1000,fail=false;const docs=new Map(),saved=new Map(),reads=[];
 class Timestamp{constructor(seconds,nanoseconds=0){this.seconds=seconds;this.nanoseconds=nanoseconds;}toMillis(){return this.seconds*1000+this.nanoseconds/1e6;}valueOf(){return this.toMillis();}static fromMillis(ms){return new Timestamp(Math.floor(ms/1000),(ms%1000)*1e6);}}
 const firebase={firestore:{Timestamp,FieldValue:{serverTimestamp:()=>({server:true})},FieldPath:{documentId:()=> '__name__'}}};
 const ref=path=>({path});
 function collection(path,filters=[],orders=[],cursor=null,limit=Infinity){
  return {doc:id=>({path:path+'/'+id,collection:name=>collection(path+'/'+id+'/'+name),get:async()=>{reads.push(path+'/'+id);return {exists:docs.has(path+'/'+id),data:()=>docs.get(path+'/'+id)};}}),
   where:(...f)=>collection(path,[...filters,f],orders,cursor,limit),orderBy:f=>collection(path,filters,[...orders,f],cursor,limit),limit:n=>collection(path,filters,orders,cursor,n),startAfter:(...v)=>collection(path,filters,orders,v,limit),get:async()=>{
    reads.push(path);const rows=[...docs].filter(([p,d])=>p.startsWith(path+'/') && p.split('/').length===path.split('/').length+1 && filters.every(([f,op,v])=>op==='>'?d[f]>v:d[f]<=v)).sort((a,b)=>a[1].at-b[1].at || a[0].localeCompare(b[0])).filter(([p,d])=>!cursor || d.at>cursor[0] || +d.at===+cursor[0] && p.split('/').at(-1)>cursor[1]).slice(0,limit);
    return {docs:rows.map(([p,d])=>({id:p.split('/').at(-1),data:()=>d}))};
   }};
 }
 const db={collection:n=>collection(n),batch:()=>{
  const ops=[];return {set:(r,d,o)=>ops.push([r,d,o]),delete:r=>ops.push([r,null]),commit:async()=>{
   const time=Timestamp.fromMillis(++clock);for(const [r,raw,o]of ops){if(raw===null)docs.delete(r.path);else{const d={...raw};if(d.at?.server)d.at=time;docs.set(r.path,o?.merge?{...docs.get(r.path),...d}:d);}}
  }};
 }};
 const options={db,firebase,storage:{getItem:k=>saved.get(k),setItem:(k,v)=>{if(fail)throw Error('quota');saved.set(k,v);}},currentUid:()=>uid,pageSize:2};
 return {options,docs,saved,reads,setUid:v=>uid=v,setFail:v=>fail=v,Timestamp};
}
const op=(id,data,extra={})=>({collection:'records',id,data,merge:false,revision:'change-'+id,...extra});
test('atomic record/delete + event + head; repeat sync reads only one head, restart retains cursor',async()=>{
 const f=fixture(),s=create(f.options),received=[];
 await s.commit('a',op('one',{lift:'bench',weight:10,createdAt:123}));
 assert.equal(f.docs.size,3);assert.equal(f.docs.get('users/a/records/one').createdAt.toMillis(),123);
 await s.sync('a',async(_,x)=>received.push(...x));assert.equal(received.length,1);
 const before=f.reads.length;await create(f.options).sync('a',async()=>assert.fail());assert.equal(f.reads.length-before,1);
 await s.commit('a',op('one',null,{revision:'delete-one'}));
 await s.sync('a',async(_,x)=>received.push(...x));assert.equal(received.at(-1).data,null);assert.ok(!f.docs.has('users/a/records/one'));
});
test('only new changes read; all pages applied before checkpoint, failed save is retryable',async()=>{
 const f=fixture(),s=create(f.options);for(let i=0;i<5;i++)await s.commit('a',op(String(i),{lift:'bench',weight:i}));
 let count=0;await assert.rejects(s.sync('a',async(_,x)=>{count+=x.length;if(count>2)throw Error('quota');}),/quota/);assert.equal(f.saved.size,0);
 count=0;await s.sync('a',async(_,x)=>{count+=x.length;});assert.equal(count,5);
 await s.commit('a',op('last',{lift:'bench',weight:99}));const got=[];await s.sync('a',async(_,x)=>got.push(...x));assert.equal(got.length,1);assert.equal(got[0].recordId,'last');
});
test('checkpoint failure, account switch, backward server head never silently advance',async()=>{
 const f=fixture(),s=create(f.options);await s.commit('a',op('one',{lift:'bench'}));f.setFail(true);await assert.rejects(s.sync('a',async()=>{}),/quota/);assert.equal(f.saved.size,0);f.setFail(false);
 await assert.rejects(s.sync('a',async()=>{f.setUid('b');}),/Account changed/);assert.equal(f.saved.size,0);
 f.setUid('a');await s.sync('a',async()=>{});f.docs.set('users/a/meta/recordUpdates',{at:f.Timestamp.fromMillis(1)});await assert.rejects(s.sync('a',async()=>{}),/backwards/);
});

test('clean-install baseline skips historic feed but receives writes after snapshot starts',async()=>{
 const f=fixture(),s=create(f.options);await s.commit('a',op('old',{lift:'bench'}));await s.prime('a');
 let count=0;await s.sync('a',async(_,x)=>{count+=x.length;});assert.equal(count,0);
 await s.commit('a',op('new',{lift:'bench'}));await s.sync('a',async(_,x)=>{count+=x.length;});assert.equal(count,1);
});
