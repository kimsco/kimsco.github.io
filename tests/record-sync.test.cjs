const {test}=require('node:test');const assert=require('node:assert/strict');const {create}=require('../js/record-sync.js');
function fixture(){
 let clock=0,uid='a',local=false,denied=false,quota=false;const stored=new Map(),server=new Map(),snapshots=new Map(),requests=[],applied=[],reads=[];
 const time=()=>`2026-10-21T00:00:00.${String(++clock).padStart(9,'0')}Z`;
 const put=(collection,id,data)=>server.set(collection+'/'+id,{...data,updatedAt:time()});
 const fetchFn=async(url,options)=>{
  if(denied)return {ok:false,status:403};
  const body=JSON.parse(options.body);requests.push(body);const q=body.structuredQuery,name=q.from[0].collectionId,rt=body.readTime||time();
  if(!snapshots.has(rt))snapshots.set(rt,new Map(server));
  const prefix=`projects/demo/databases/(default)/documents/users/${uid}/`;
  let rows=[...snapshots.get(rt)].filter(([id,d])=>id.startsWith(name+'/') && (!q.where || d.updatedAt && d.updatedAt>q.where.fieldFilter.value.timestampValue));
  const orders=q.orderBy.map(x=>x.field.fieldPath),value=([id,d],field)=>field==='__name__'?prefix+id:d[field];
  const compare=(row,bounds)=>{for(let i=0;i<orders.length;i++){const a=value(row,orders[i]),b=bounds[i];if(a!==b)return a<b?-1:1;}return 0;};
  rows.sort((a,b)=>compare(a,orders.map(field=>value(b,field))));
  if(q.startAt)rows=rows.filter(row=>compare(row,q.startAt.values.map(v=>v.timestampValue||v.referenceValue))>0);
  const page=rows.slice(0,q.limit).map(([id,data])=>({document:{name:prefix+id,fields:{...data,updatedAt:data.updatedAt?{timestampValue:data.updatedAt}:undefined}},readTime:rt}));
  return {ok:true,json:async()=>page.length?page:[{readTime:rt}]};
 };
 const auth={get currentUser(){return uid?{uid,getIdToken:async()=> 'token'}:null;}};
 const options={auth,projectId:'demo',storage:{getItem:k=>stored.get(k),setItem:(k,v)=>{if(quota)throw Error('quota');stored.set(k,v);}},hasLocal:()=>local,decode:x=>x,fetchFn,pageSize:2,onRead:x=>reads.push(x),apply:async(owner,rows,ops)=>{applied.push({owner,rows,ops});local=true;}};
 return {options,server,stored,requests,applied,reads,put,setUid:x=>uid=x,setDenied:x=>denied=x,setQuota:x=>quota=x,setLocal:x=>local=x};
}
test('one baseline includes legacy rows, pins pages to server time, then two empty queries on restart',async()=>{
 const f=fixture();for(let i=0;i<5;i++)f.server.set('records/'+i,{weight:i});
 await create(f.options).sync('a');assert.equal(f.applied[0].rows[0].docs.length,5);assert.equal(f.applied[0].rows[0].full,true);
 assert.equal(f.requests[1].readTime,f.requests[2].readTime);assert.ok(f.requests[1].readTime);
 f.requests.length=0;f.reads.length=0;await create(f.options).sync('a');assert.equal(f.requests.length,2);assert.deepEqual(f.reads.map(x=>x.count),[0,0]);
 assert.equal(f.applied.at(-1).rows[0].full,false);assert.ok(f.requests[0].structuredQuery.where.fieldFilter.value.timestampValue.endsWith('000000001Z'));
});
test('updates, additions and deletion markers arrive without original history replay',async()=>{
 const f=fixture(),s=create(f.options);f.server.set('records/legacy',{weight:50});await s.sync('a');
 f.put('records','legacy',{weight:60});f.put('records','new',{weight:80});f.put('accessoryRecords','gone',{deleted:true});
 await s.sync('a');const rows=f.applied.at(-1).rows;
 assert.equal(rows[0].docs.length,2);assert.equal(rows[1].docs.length,1);assert.equal(rows[1].docs[0].data.deleted,true);
 f.setLocal(false);await s.sync('a');assert.equal(f.applied.at(-1).rows[0].full,true);
});
test('denied/offline, apply failure and missing server time never advance checkpoint',async()=>{
 const f=fixture(),s=create(f.options);f.setDenied(true);await assert.rejects(s.sync('a'),/403/);assert.equal(f.stored.size,0);f.setDenied(false);
 f.options.apply=async()=>{throw Error('quota');};await assert.rejects(create(f.options).sync('a'),/quota/);assert.equal(f.stored.size,0);
 f.options.fetchFn=async()=>({ok:true,json:async()=>[]});await assert.rejects(create(f.options).sync('a'),/snapshot time/);assert.equal(f.stored.size,0);
});
test('single flight, writes during download, and account switch safety',async()=>{
 const f=fixture();let release;const original=f.options.fetchFn;
 f.options.fetchFn=async(...args)=>{await new Promise(r=>release=r);return original(...args);};
 const s=create(f.options),first=s.sync('a');assert.equal(first,s.sync('a'));
 await new Promise(setImmediate);s.noteLocalWrite('a',{'records/one':{collection:'records',id:'one',data:{weight:90}}});release();
 await new Promise(setImmediate);release();await first;assert.equal(f.applied[0].ops['records/one'].data.weight,90);
 const second=s.sync('a');await new Promise(setImmediate);f.setUid('b');release();await assert.rejects(second,/Account changed/);
 assert.equal(f.applied.length,1);
});
test('a timed out token cannot issue a late request or apply a result',async()=>{
 const f=fixture();let release,calls=0;f.options.auth={currentUser:{uid:'a',getIdToken:()=>new Promise(r=>release=r)}};f.options.timeoutMs=5;f.options.fetchFn=async()=>{calls++;};
 await assert.rejects(create(f.options).sync('a'),/timeout/);release('token');await new Promise(setImmediate);assert.equal(calls,0);assert.equal(f.applied.length,0);
});
