/* Isolated browser fixture. Never contacts production Firebase or deletes real accounts. */
(() => {
  let store; const calls = []; let online = true; let denied = false; let reauthError = false; let deleteError = false;
  class Timestamp {constructor(ms){this.ms=ms;}toMillis(){return this.ms;}static fromMillis(ms){return new Timestamp(ms);}}
  class FieldValue {static serverTimestamp(){return new FieldValue();}}
  const persisted=localStorage.getItem('fixture_persist_server')==='1';
  const encode=(key,value)=>value?.toMillis?{__fixtureTimestamp:value.toMillis()}:value;
  const decode=(key,value)=>value && Object.keys(value).length===1 && '__fixtureTimestamp' in value?Timestamp.fromMillis(value.__fixtureTimestamp):value;
  class FixtureStore extends Map {
    set(key,value){super.set(key,value);this.persist();return this;}
    delete(key){const result=super.delete(key);this.persist();return result;}
    clear(){super.clear();this.persist();}
    persist(){if(persisted)localStorage.setItem('fixture_server_v1',JSON.stringify([...this],encode));}
  }
  store=new FixtureStore();
  if(persisted)for(const [key,value] of JSON.parse(localStorage.getItem('fixture_server_v1')||'[]',decode))Map.prototype.set.call(store,key,value);
  const docSnap = (path,data) => ({id:path.split('/').at(-1),exists:data!==undefined,ref:ref(path),data:()=>data});
  function ref(path){return {path,id:path.split('/').at(-1),collection:n=>query(path+'/'+n),get:async(options)=>{calls.push({path,type:'get',source:options?.source});if(options?.source==='server'&&(!online||denied))throw Error('fixture unavailable');return docSnap(path,store.get(path));},
    set:async(data,opts)=>{calls.push({path,type:'set'});if(!online||denied)throw Error('fixture unavailable');store.set(path,opts?.merge?{...store.get(path),...data}:data);},
    delete:async()=>{calls.push({path,type:'delete'});if(!online||denied)throw Error('fixture unavailable');store.delete(path);}};}
  function query(path,filters=[],maximum=Infinity,orders=[],after=null){return {doc:id=>ref(path+'/'+id),where:(field,op,value)=>query(path,[...filters,[field,op,value]],maximum,orders,after),orderBy:(field,direction='asc')=>query(path,filters,maximum,[...orders,[field,direction]],after),limit:n=>query(path,filters,n,orders,after),startAfter:doc=>query(path,filters,maximum,orders,doc),
    get:async(options)=>{calls.push({path,type:'query',source:options?.source,filters});if(options?.source==='server'&&(!online||denied))throw Error('fixture unavailable');const docs=[...store].filter(([key,data])=>key.startsWith(path+'/')&&key.split('/').length===path.split('/').length+1&&filters.every(([field,op,value])=>{const v=field==='__id__'?key.split('/').at(-1):data[field];return op==='=='?v===value:op==='>='?v>=value:op==='<='?v<=value:op==='<'?v<value:op==='>'?v>value:true;})).sort((a,b)=>{for(const [field,direction] of orders){const av=a[1][field]?.toMillis?.()??a[1][field],bv=b[1][field]?.toMillis?.()??b[1][field];if(av!==bv)return (av<bv?-1:1)*(direction==='desc'?-1:1);}return a[0].localeCompare(b[0]);}).filter(([key,data])=>{if(!after)return true;for(const [field,direction] of orders){const av=data[field],bv=after.data()[field];if(av!==bv)return direction==='desc'?av<bv:av>bv;}return key.split('/').at(-1)>after.id;}).slice(0,maximum).map(([key,data])=>docSnap(key,data));return {docs,empty:!docs.length,forEach:fn=>docs.forEach(fn)};}};}
  const db={settings:options=>calls.push({type:'settings',options}),collection:n=>query(n),enablePersistence:async()=>{},waitForPendingWrites:async()=>{},batch:()=>{const ops=[];return {delete:r=>ops.push(()=>r.delete()),update:(r,d)=>ops.push(()=>r.set(d,{merge:true})),commit:async()=>{for(const op of ops)await op();}};}};
  let transactions=Promise.resolve();
  db.runTransaction=fn=>{
    const work=transactions.catch(()=>{}).then(async()=>{
      if(!online||denied)throw Error('fixture unavailable');
      const ops=[],paths=[];
      const tx={get:r=>r.get({source:'server'}),set:(r,d)=>{paths.push(r.path);ops.push(()=>r.set(d));},delete:r=>{paths.push(r.path);ops.push(()=>r.delete());}};
      const result=await fn(tx),previous=new Map(store);
      if(localStorage.getItem('fixture_deny_record_changes')==='1' && paths.some(path=>path.includes('/recordChanges/'))){const error=Error('fixture denied');error.code='permission-denied';throw error;}
      try{for(const op of ops)await op();}catch(e){store.clear();for(const [k,v] of previous)store.set(k,v);throw e;}
      return result;
    });transactions=work;return work;
  };
  const listeners=[];
  const uid=localStorage.getItem('fixture_uid');
  const auth={currentUser:uid?{uid,email:uid+'@example.test',displayName:uid,reauthenticateWithPopup:async()=>{if(reauthError)throw Error('fixture reauthentication canceled');},delete:async()=>{if(deleteError)throw Error('fixture auth deletion failed');localStorage.removeItem('fixture_uid');auth.currentUser=null;listeners.forEach(fn=>fn(null));}}:null,onAuthStateChanged:fn=>{listeners.push(fn);setTimeout(()=>fn(auth.currentUser),0);},signOut:async()=>{localStorage.removeItem('fixture_uid');auth.currentUser=null;listeners.forEach(fn=>fn(null));}};
  const firestore=()=>db;Object.assign(firestore,{Timestamp,FieldValue,FieldPath:{documentId:()=> '__id__'}});
  const authFn=()=>auth;authFn.GoogleAuthProvider=class {};
  window.firebase={initializeApp:()=>{},auth:authFn,firestore};
  window.fixture={store,calls,setReauthError:v=>reauthError=v,setDeleteError:v=>deleteError=v,setOnline:v=>online=v,setDenied:v=>denied=v,auth};
})();
