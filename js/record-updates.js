/* A small update head plus durable change pages; original history is never polled. */
(function(root){
 'use strict';
 function create({db,firebase,storage,currentUid,pageSize=200}){
  const pending=new Map();
  const user=uid=>db.collection('users').doc(uid);
  const key=uid=>`mf_account_v2:${uid}:record_update_cursor_v1`;
  const encode=t=>({seconds:t.seconds??Math.floor(t.toMillis()/1000),nanoseconds:t.nanoseconds??Math.round((t.toMillis()%1000)*1e6)});
  const decode=t=>new firebase.firestore.Timestamp(t.seconds,t.nanoseconds);
  const compare=(a,b)=>a.seconds-b.seconds || a.nanoseconds-b.nanoseconds;
  function check(uid){if(currentUid()!==uid)throw Error('Account changed');}
  async function commit(uid,op){
   check(uid);
   const batch=db.batch(),ref=user(uid).collection(op.collection).doc(op.id);
   if(op.data===null)batch.delete(ref);
   else {
    const data={...op.data};
    if(Number.isFinite(data.createdAt))data.createdAt=firebase.firestore.Timestamp.fromMillis(data.createdAt);
    batch.set(ref,data,{merge:op.merge});
   }
   const at=firebase.firestore.FieldValue.serverTimestamp();
   batch.set(user(uid).collection('recordUpdates').doc(op.revision),{
    collection:op.collection,recordId:op.id,data:op.data,merge:op.merge,at
   });
   batch.set(user(uid).collection('meta').doc('recordUpdates'),{at});
   await batch.commit();
  }
  async function prime(uid){
   check(uid);
   if(storage.getItem(key(uid)))return;
   const marker=await user(uid).collection('meta').doc('recordUpdates').get({source:'server'});check(uid);
   if(marker.exists && marker.data().at)storage.setItem(key(uid),JSON.stringify(encode(marker.data().at)));
  }
  function sync(uid,apply){
   if(pending.has(uid))return pending.get(uid);
   const work=(async()=>{
    check(uid);
    const marker=await user(uid).collection('meta').doc('recordUpdates').get({source:'server'});check(uid);
    if(!marker.exists || !marker.data().at)return false;
    const end=encode(marker.data().at);
    let saved;try{saved=JSON.parse(storage.getItem(key(uid))||'null');}catch(e){}
    if(saved && compare(saved,end)===0)return false;
    // A server restore to an older head must not silently discard local history.
    if(saved && compare(saved,end)>0)throw Error('Record update head moved backwards');
    let cursor=null,changed=false;
    while(true){
     let q=user(uid).collection('recordUpdates').where('at','<=',decode(end));
     if(saved)q=q.where('at','>',decode(saved));
     q=q.orderBy('at').orderBy(firebase.firestore.FieldPath.documentId()).limit(pageSize);
     if(cursor)q=q.startAfter(cursor.at,cursor.id);
     const snap=await q.get({source:'server'});check(uid);
     const changes=snap.docs.map(doc=>doc.data());
     if(changes.length){await apply(uid,changes);check(uid);changed=true;}
     if(snap.docs.length<pageSize)break;
     const last=snap.docs.at(-1);cursor={at:last.data().at,id:last.id};
    }
    // Advance only after every page has reached durable account-local storage.
    storage.setItem(key(uid),JSON.stringify(end));
    return changed;
   })().finally(()=>pending.delete(uid));
   pending.set(uid,work);return work;
  }
  return {commit,sync,prime};
 }
 const api={create};if(typeof module!=='undefined')module.exports=api;root.MFRecordUpdates=api;
})(typeof window==='undefined'?globalThis:window);
