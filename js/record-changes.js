/* Account-scoped, atomic last-change feed for records; no background polling. */
(function(root){
 'use strict';
 const COLLECTIONS=['records','accessoryRecords'];
 const valid=s=>s?.schema===1 && typeof s.epoch==='string' && Number.isSafeInteger(s.version) && s.version>=0;
 function createService({db,storage,currentUid,isDeleting=()=>false,clean=x=>x,online=()=>true,now=()=>Date.now(),checkMs=30000,reconcileMs=86400000,onRead=()=>{},onCommit=()=>{}}){
  const initialized=new Map(),initializing=new Map(),syncing=new Map(),checked=new Map(),firstState=new Map();
  const user=uid=>db.collection('users').doc(uid);
  const meta=uid=>user(uid).collection('meta').doc('recordSync');
  const feed=uid=>user(uid).collection('recordChanges');
  const cursorKey=uid=>'mf_account_v2:'+uid+':record_cursor_v1';
  const read=async target=>{const snap=await target.get({source:'server'});onRead(snap);return snap;};
  const txRead=async(tx,target)=>{const snap=await tx.get(target);onRead(snap);return snap;};
  const check=uid=>{if(!uid || currentUid()!==uid || isDeleting(uid))throw Error('Account changed or deleting');};
  async function ensure(uid){
   check(uid);if(initialized.has(uid))return initialized.get(uid);if(initializing.has(uid))return initializing.get(uid);
   const task=(async()=>{
    if(!online())throw Error('Offline');
    const snap=await read(meta(uid));check(uid);
    if(snap.exists){if(!valid(snap.data()))throw Error('Unsupported record sync schema');firstState.set(uid,snap.data());initialized.set(uid,true);return true;}
    const initial=await db.runTransaction(async tx=>{
     const existing=await txRead(tx,meta(uid));check(uid);
     if(existing.exists){if(!valid(existing.data()))throw Error('Unsupported record sync schema');return existing.data();}
     const epoch=root.crypto.randomUUID();
     const value={schema:1,epoch,version:0,clients:{}};
     tx.set(meta(uid),value);
     // An empty protocol marker also verifies permission to create the private feed.
     tx.set(feed(uid).doc('protocol'),{schema:1,epoch,version:0,protocol:true});
     return value;
    });check(uid);firstState.set(uid,initial);initialized.set(uid,true);return true;
   })().catch(error=>{
    if(String(error.code||'').endsWith('permission-denied')){initialized.set(uid,false);return false;}
    throw error;
   }).finally(()=>initializing.delete(uid));initializing.set(uid,task);return task;
  }
  async function changeRef(uid,collection,id){
   const bytes=new TextEncoder().encode(collection+'/'+id);
   const digest=await root.crypto.subtle.digest('SHA-256',bytes);
   return feed(uid).doc(Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join(''));
  }
  function identity(op){if(!op.clientId || !Number.isSafeInteger(op.clientSeq) || op.clientSeq<=0)throw Error('Missing durable operation identity');}
  async function write(uid,op){
   if(!COLLECTIONS.includes(op.collection))return false;
   if(!await ensure(uid))return false;
   identity(op);check(uid);
   const target=user(uid).collection(op.collection).doc(op.id);
   const event=await changeRef(uid,op.collection,op.id);check(uid);
   const committed=await db.runTransaction(async tx=>{
    const snap=await txRead(tx,meta(uid));check(uid);const state=snap.data();if(!valid(state))throw Error('Invalid sync state');
    if((state.clients?.[op.clientId]||0)>=op.clientSeq){
     const latest=await txRead(tx,event);check(uid);
     return {epoch:state.epoch,fromVersion:state.version,toVersion:state.version,complete:false,changes:latest.exists?[latest.data()]:[]};
    }
    let data=op.data;
    if(data!==null && op.merge){
     const old=await txRead(tx,target),previous=await txRead(tx,event);check(uid);
     // A delayed edit cannot resurrect a record already deleted on another device.
     if(!old.exists && previous.exists && previous.data().deleted){
      tx.set(meta(uid),{...state,clients:{...state.clients,[op.clientId]:op.clientSeq}});
      return {epoch:state.epoch,fromVersion:state.version,toVersion:state.version,complete:false,changes:[previous.data()]};
     }
     data={...(old.exists?old.data():{}),...data};
    }
    const version=state.version+1;
    if(data===null)tx.delete(target);else tx.set(target,data);
    const change={schema:1,epoch:state.epoch,version,collection:op.collection,id:op.id,deleted:data===null,data:data===null?null:clean(data)};
    tx.set(event,change);
    tx.set(meta(uid),{...state,version,clients:{...state.clients,[op.clientId]:op.clientSeq}});
    return {epoch:state.epoch,fromVersion:state.version,toVersion:version,complete:true,changes:[change]};
   });check(uid);firstState.delete(uid);checked.delete(uid);if(committed)onCommit(uid,committed);return true;
  }
  async function acknowledged(uid,op){
   if(!await ensure(uid))return false;
   const snap=await read(meta(uid));check(uid);
   return (snap.data()?.clients?.[op.clientId]||0)>=op.clientSeq;
  }
  async function writeGroup(uid,op,documents,{finish=false}={}){
   if(op.collection!=='accessoryRecords' || !await ensure(uid))return false;
   identity(op);if(documents.length>200)throw Error('Group exceeds safe batch size');
   const refs=await Promise.all(documents.map(doc=>changeRef(uid,op.collection,doc.id)));check(uid);
   const committed=await db.runTransaction(async tx=>{
    const snap=await txRead(tx,meta(uid));check(uid);const state=snap.data();if(!valid(state))throw Error('Invalid sync state');
    if((state.clients?.[op.clientId]||0)>=op.clientSeq)return;
    const snapshots=op.data===null?null:await Promise.all(documents.map(doc=>txRead(tx,doc.ref)));check(uid);
    const version=state.version+(documents.length?1:0);
    const changes=[];
    documents.forEach((doc,index)=>{
     if(snapshots && !snapshots[index].exists)return;
     const data=op.data===null?null:{...snapshots[index].data(),...op.data};
     if(data===null)tx.delete(doc.ref);else tx.set(doc.ref,data);
     const change={schema:1,epoch:state.epoch,version,collection:op.collection,id:doc.id,deleted:data===null,data:data===null?null:clean(data)};
     tx.set(refs[index],change);changes.push(change);
    });
    tx.set(meta(uid),{...state,version,clients:finish?{...state.clients,[op.clientId]:op.clientSeq}:state.clients||{}});
    return {epoch:state.epoch,fromVersion:state.version,toVersion:version,complete:true,changes};
   });check(uid);firstState.delete(uid);checked.delete(uid);if(committed)onCommit(uid,committed);return true;
  }
  const deletedKey=uid=>'mf_account_v2:'+uid+':record_deleted_v1';
  function deletedRows(uid){try{return JSON.parse(storage.getItem(deletedKey(uid))||'{}');}catch(e){return {};}}
  function noteApplied(uid,changes){
   check(uid);const rows=deletedRows(uid);
   for(const change of changes){
    const key=change.collection+'/'+change.id;
    if(change.deleted)rows[key]=change.version;else delete rows[key];
   }
   if(changes.length)storage.setItem(deletedKey(uid),JSON.stringify(rows));
  }
  function filterSnapshot(uid,collection,snap){
   if(!COLLECTIONS.includes(collection))return snap;
   const deleted=deletedRows(uid);
   if(snap.docs){const docs=snap.docs.filter(doc=>!deleted[collection+'/'+doc.id]);return {...snap,docs,empty:!docs.length,forEach:fn=>docs.forEach(fn)};}
   return deleted[collection+'/'+snap.id]?{id:snap.id,exists:false}:snap;
  }
  function readCursor(uid){try{return JSON.parse(storage.getItem(cursorKey(uid))||'null');}catch(e){return null;}}
  function advanceOwn(uid,commits){
   check(uid);const cursor=readCursor(uid);if(!cursor)return;
   let version=cursor.version;
   for(const commit of commits){
    if(commit.complete && commit.epoch===cursor.epoch && commit.fromVersion===version)version=commit.toVersion;
   }
   if(version!==cursor.version)storage.setItem(cursorKey(uid),JSON.stringify({...cursor,version}));
   if(commits.every(commit=>commit.epoch===cursor.epoch && commit.complete && commit.toVersion<=version))checked.set(uid,now());
  }
  function sync(uid,{hasLocal,bootstrap,apply,force=false}){
   if(syncing.has(uid))return syncing.get(uid);
   const task=(async()=>{
    check(uid);if(!online())return {mode:'offline'};
    if(!force && checked.has(uid) && now()>=checked.get(uid) && now()-checked.get(uid)<checkMs && hasLocal())return {mode:'cached'};
    if(!await ensure(uid))return {mode:'legacy'};
    const observed=firstState.get(uid);firstState.delete(uid);
    const state=observed || (await read(meta(uid))).data();check(uid);if(!valid(state))throw Error('Invalid sync state');
    let cursor=readCursor(uid);
    if(!hasLocal() || cursor?.epoch!==state.epoch || !Number.isSafeInteger(cursor?.version) || cursor.version>state.version || !Number.isFinite(cursor.scannedAt) || cursor.scannedAt<=0 || now()<cursor.scannedAt || now()-cursor.scannedAt>=reconcileMs){
     await bootstrap({version:state.version,epoch:state.epoch});check(uid);
     cursor={epoch:state.epoch,version:state.version,scannedAt:now()};
     storage.setItem(cursorKey(uid),JSON.stringify(cursor));checked.set(uid,now());return {mode:'bootstrap',version:cursor.version};
    }
    if(cursor.version===state.version){checked.set(uid,now());return {mode:'unchanged',version:cursor.version};}
    let last;let count=0;
    while(true){
     let query=feed(uid).where('version','>',cursor.version).where('version','<=',state.version).orderBy('version').limit(200);
     if(last)query=query.startAfter(last);
     const page=await read(query);check(uid);
     const changes=page.docs.map(doc=>doc.data()).filter(event=>event.epoch===state.epoch && COLLECTIONS.includes(event.collection));
     await apply(changes);check(uid);count+=changes.length;
     if(page.docs.length<200)break;last=page.docs.at(-1);
    }
    // Cache persistence must succeed before advancing this cursor; replay is idempotent.
    storage.setItem(cursorKey(uid),JSON.stringify({...cursor,version:state.version}));checked.set(uid,now());return {mode:'delta',count,version:state.version};
   })().finally(()=>syncing.delete(uid));syncing.set(uid,task);return task;
  }
  return {ensure,write,writeGroup,acknowledged,sync,readCursor,advanceOwn,noteApplied,filterSnapshot,idle:uid=>Promise.allSettled([initializing.get(uid),syncing.get(uid)].filter(Boolean))};
 }
 const api={createService};if(typeof module!=='undefined')module.exports=api;root.MFRecordChanges=api;
})(typeof window==='undefined'?globalThis:window);
