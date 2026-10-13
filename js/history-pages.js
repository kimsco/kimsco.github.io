/* Durable account-scoped cursors; write cache before advancing the server page. */
(function(root){
 'use strict';
 function create({storage,currentUid,hasLocal,fullFresh,query,apply,now=()=>Date.now(),ttlMs=86400000,daysPerPage=4,dayChunkSize=100}){
  const pending=new Map();
  const key=(uid,kind,name)=>'mf_account_v2:'+uid+':read_fresh:historyPage:'+JSON.stringify([kind,name]);
  function state(uid,kind,name){
   if(fullFresh(uid,kind,name))return {done:true};
   try{const s=JSON.parse(storage.getItem(key(uid,kind,name))||'null');if(s?.schema===2 && hasLocal(kind,name) && now()>=s.at && now()-s.at<ttlMs && typeof s.before==='string' && (!s.cursor || typeof s.cursor.date==='string' && typeof s.cursor.id==='string'))return s;}catch(e){}
   return null;
  }
  function done(kind,name){const uid=currentUid();return !uid || !!state(uid,kind,name)?.done;}
  function next(kind,name,before){
   const uid=currentUid();if(!uid)return Promise.resolve(false);
   const id=key(uid,kind,name);if(pending.has(id))return pending.get(id);
   const check=()=>{if(currentUid()!==uid)throw Error('Account changed');};
   const task=(async()=>{
    check();const previous=state(uid,kind,name);if(previous?.done)return false;
    const s=previous || {schema:2,before,cursor:null,done:false};
    const startedAt=now();const docs=[];let cursor=s.cursor,exhausted=false;
    for(let dayIndex=0;dayIndex<daysPerPage;dayIndex++){
     const first=await query(uid,kind,name,{before:s.before,cursor,limit:1});check();
     if(!first.docs.length){exhausted=true;break;}
     const head=first.docs[0],date=head.data().date;docs.push(head);cursor={date,id:head.id};
     // Fetch only this workout day. Never read a fifth date as look-ahead.
     while(true){
      const rest=await query(uid,kind,name,{before:s.before,date,cursor,limit:dayChunkSize});check();
      docs.push(...rest.docs);const last=rest.docs.at(-1);if(last)cursor={date,id:last.id};
      if(rest.docs.length<dayChunkSize)break;
     }
    }
    const snap={docs};
    // Atomic cursor ordering: a quota failure leaves this page retryable.
    const changed=await apply(uid,kind,name,snap,{before:s.before,cursor:s.cursor,startedAt,exhausted});check();
    storage.setItem(id,JSON.stringify({...s,cursor,done:exhausted,at:previous?.at || now()}));
    return changed;
   })().finally(()=>pending.delete(id));pending.set(id,task);return task;
  }
  return {next,done};
 }
 const api={create};if(typeof module!=='undefined')module.exports=api;root.MFHistoryPages=api;
})(typeof window==='undefined'?globalThis:window);
