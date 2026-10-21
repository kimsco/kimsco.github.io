/* Server-read-time checkpoints; one original document write, including tombstones. */
(function(root){
 'use strict';
 const collections=['records','accessoryRecords'];
 const validTime=t=>typeof t==='string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/.test(t) && Number.isFinite(Date.parse(t));
 function create({auth,projectId,storage,hasLocal,apply,decode,readPending=()=>({}),isDeleting=()=>false,fetchFn=(...args)=>root.fetch(...args),pageSize=200,timeoutMs=12000,onRead=()=>{}}){
  const running=new Map();
  const key=(uid,name)=>`mf_account_v2:${uid}:record_sync_v1:${name}`;
  const check=uid=>{if(auth.currentUser?.uid!==uid || isDeleting(uid))throw Error('Account changed');};
  const checkpoint=(uid,name)=>{
   if(!hasLocal(name))return null;
   try{const saved=JSON.parse(storage.getItem(key(uid,name)));return saved?.schema===1 && validTime(saved.readTime)?saved.readTime:null;}catch(e){return null;}
  };
  async function request(uid,body){
   check(uid);const controller=new AbortController();let timer;
   try{return await Promise.race([
    (async()=>{
     const token=await auth.currentUser.getIdToken();check(uid);
     if(controller.signal.aborted)throw Error('Record sync timeout');
     const parent=`projects/${projectId}/databases/(default)/documents/users/${uid}`;
     const url=`https://firestore.googleapis.com/v1/projects/${encodeURIComponent(projectId)}/databases/(default)/documents/users/${encodeURIComponent(uid)}:runQuery`;
     const response=await fetchFn(url,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store',signal:controller.signal});check(uid);
     if(!response.ok)throw Error('Record sync HTTP '+response.status);
     const rows=await response.json();check(uid);
     if(controller.signal.aborted)throw Error('Record sync timeout');
     if(!Array.isArray(rows) || rows.some(row=>row.error))throw Error('Invalid record sync response');
     return {rows,parent};
    })(),
    new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('Record sync timeout'));},timeoutMs);})
   ]);}finally{clearTimeout(timer);controller.abort();}
  }
  function sync(uid){
   if(running.has(uid))return running.get(uid).promise;
   const active={ops:{...readPending(uid)}};
   const promise=(async()=>{
    check(uid);const snapshots=[];
    // Each collection has its own precise server checkpoint, never a phone-clock time.
    for(const name of collections){
     const since=checkpoint(uid,name),docs=[];let readTime=null,cursor=null;
     while(true){
      const query={from:[{collectionId:name}],orderBy:since?[{field:{fieldPath:'updatedAt'},direction:'ASCENDING'},{field:{fieldPath:'__name__'},direction:'ASCENDING'}]:[{field:{fieldPath:'__name__'},direction:'ASCENDING'}],limit:pageSize};
      if(since)query.where={fieldFilter:{field:{fieldPath:'updatedAt'},op:'GREATER_THAN',value:{timestampValue:since}}};
      if(cursor)query.startAt={values:cursor,before:false};
      const body={structuredQuery:query};if(readTime)body.readTime=readTime;
      const result=await request(uid,body);check(uid);
      const times=result.rows.map(row=>row.readTime).filter(validTime);
      if(!times.length)throw Error('Missing record snapshot time');
      if(!readTime)readTime=times.at(-1);
      const page=result.rows.filter(row=>row.document).map(row=>row.document);
      onRead({collection:name,count:page.length});
      for(const document of page){
       if(!document.name.startsWith(result.parent+'/'+name+'/') || document.name.slice((result.parent+'/'+name+'/').length).includes('/'))throw Error('Invalid record document owner');
       docs.push({id:document.name.split('/').at(-1),data:decode(document.fields||{})});
      }
      if(page.length<pageSize)break;
      const last=page.at(-1);cursor=since?[last.fields.updatedAt,{referenceValue:last.name}]:[{referenceValue:last.name}];
      if(cursor.some(value=>!value))throw Error('Missing record page cursor');
     }
     snapshots.push({collection:name,full:!since,docs,readTime});
    }
    check(uid);
    // Writes accepted even while queries were in flight must win over that snapshot.
    await apply(uid,snapshots,{...active.ops,...readPending(uid)});check(uid);
    for(const snap of snapshots)storage.setItem(key(uid,snap.collection),JSON.stringify({schema:1,readTime:snap.readTime}));
    return true;
   })().finally(()=>{if(running.get(uid)===active)running.delete(uid);});
   active.promise=promise;running.set(uid,active);return promise;
  }
  function noteLocalWrite(uid,ops){const active=running.get(uid);if(active)Object.assign(active.ops,ops);}
  return {sync,noteLocalWrite};
 }
 const api={create,validTime};if(typeof module!=='undefined')module.exports=api;root.MFRecordSync=api;
})(typeof window==='undefined'?globalThis:window);
