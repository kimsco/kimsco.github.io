/* Page-scoped freshness and single-flight reads; no user data or IDs in statistics. */
(function(root){
 'use strict';
 function create({now=()=>Date.now(),ttlMs=300000,storage}={}){
  const entries=new Map();const stats={started:0,reused:0,shared:0,failed:0,returnedDocuments:0,estimatedServerReads:0,cacheDocuments:0};
  function run(owner,key,read,{reuse,hasLocal,ttlMs:resourceTtl=ttlMs}={}){
   const id=JSON.stringify([owner,key]);const previous=entries.get(id);
   const stampKey='mf_account_v2:'+owner+':read_fresh:'+key;
   if(!previous && storage && hasLocal?.()){
    try{const at=Number(storage.getItem(stampKey));if(at>0 && now()>=at && now()-at<resourceTtl){stats.reused++;return Promise.resolve(reuse?reuse():undefined);}}catch(e){}
   }
   if(previous?.pending){stats.shared++;return previous.pending;}
   if(previous && (!hasLocal || hasLocal()) && now()>=previous.at && now()-previous.at<resourceTtl){stats.reused++;return Promise.resolve(reuse?reuse():previous.value);}
   const entry={at:-Infinity};stats.started++;
   const task=Promise.resolve().then(read).then(value=>{entry.at=now();entry.value=value;try{storage?.setItem(stampKey,String(entry.at));}catch(e){}delete entry.pending;return value;},error=>{stats.failed++;if(entries.get(id)===entry)entries.delete(id);throw error;});
   entry.pending=task;entries.set(id,entry);return task;
  }
  function noteSnapshot(snap){
   const count=Array.isArray(snap.docs)?snap.docs.length:snap.exists?1:0;
   stats.returnedDocuments+=count;
   if(snap.metadata?.fromCache)stats.cacheDocuments+=count;else stats.estimatedServerReads+=Math.max(1,count);
  }
  return {run,noteSnapshot,report:()=>({...stats}),clear:()=>entries.clear()};
 }
 const api={create};if(typeof module!=='undefined')module.exports=api;root.MFReadCache=api;
})(typeof window==='undefined'?globalThis:window);
