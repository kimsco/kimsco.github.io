/* Isolated browser fixture. Never contacts production Firebase or deletes real accounts. */
(() => {
  let commitTime=0,activeCommitTime=0;const store = new Map(); const calls = []; let online = true; let denied = false; let reauthError = false; let deleteError = false;
  class Timestamp {constructor(seconds,nanoseconds){this.ms=nanoseconds===undefined?seconds:seconds*1000+nanoseconds/1e6;this.seconds=Math.floor(this.ms/1000);this.nanoseconds=Math.round((this.ms%1000)*1e6);}toMillis(){return this.ms;}valueOf(){return this.ms;}static fromMillis(ms){return new Timestamp(ms);}}
  class FieldValue {static serverTimestamp(){return new FieldValue();}}
  const docSnap = (path,data) => ({id:path.split('/').at(-1),exists:data!==undefined,ref:ref(path),data:()=>data});
  function ref(path){return {path,id:path.split('/').at(-1),collection:n=>query(path+'/'+n),get:async(options)=>{calls.push({path,type:'get',source:options?.source});if(options?.source==='server'&&(!online||denied))throw Error('fixture unavailable');return docSnap(path,store.get(path));},
    set:async(data,opts)=>{calls.push({path,type:'set'});if(!online||denied)throw Error('fixture unavailable');const resolve=v=>v instanceof FieldValue?Timestamp.fromMillis(activeCommitTime || Date.now()):Array.isArray(v)?v.map(resolve):v && typeof v==='object' && !(v instanceof Timestamp)?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,resolve(x)])):v;data=resolve(data);store.set(path,opts?.merge?{...store.get(path),...data}:data);},
    delete:async()=>{calls.push({path,type:'delete'});if(!online||denied)throw Error('fixture unavailable');store.delete(path);}};}
  function query(path,filters=[],maximum=Infinity,orders=[],cursor=null){
    const build=(f=filters,m=maximum,o=orders,c=cursor)=>query(path,f,m,o,c);
    const value=(key,data,field)=>field==='__id__'?key.split('/').at(-1):data[field];
    const compare=(entry,bounds)=>{for(let i=0;i<orders.length;i++){const [field,dir]=orders[i],v=value(...entry,field),b=bounds[i];if((v instanceof Timestamp?v.toMillis():v)!==(b instanceof Timestamp?b.toMillis():b))return (v<b?-1:1)*(dir==='desc'?-1:1);}return 0;};
    return {doc:id=>ref(path+'/'+id),where:(field,op,v)=>build([...filters,[field,op,v]]),orderBy:(field,dir='asc')=>build(filters,maximum,[...orders,[field,dir]]),limit:n=>build(filters,n),startAfter:(...v)=>build(filters,maximum,orders,v),
    get:async(options)=>{calls.push({path,type:'query',source:options?.source,filters,maximum,orders});if(options?.source==='server'&&(!online||denied))throw Error('fixture unavailable');
      let entries=[...store].filter(([key,data])=>key.startsWith(path+'/')&&key.split('/').length===path.split('/').length+1&&filters.every(([field,op,v])=>{const x=value(key,data,field);return op==='=='?x===v:op==='>='?x>=v:op==='<='?x<=v:op==='<'?x<v:op==='>'?x>v:true;}));
      if(orders.length)entries.sort((a,b)=>compare(a,orders.map(([f])=>value(...b,f))));
      if(cursor)entries=entries.filter(e=>compare(e,cursor)>0);
      const docs=entries.slice(0,maximum).map(([key,data])=>docSnap(key,data));return {docs,empty:!docs.length,forEach:fn=>docs.forEach(fn)};
    }};
  }
  const db={settings:options=>calls.push({type:'settings',options}),collection:n=>query(n),enablePersistence:async()=>{},waitForPendingWrites:async()=>{},batch:()=>{const ops=[];return {set:(r,d,o)=>ops.push(()=>r.set(d,o)),delete:r=>ops.push(()=>r.delete()),update:(r,d)=>ops.push(()=>r.set(d,{merge:true})),commit:async()=>{const previous=new Map(store);activeCommitTime=commitTime=Math.max(commitTime+1,Date.now());try{for(const op of ops)await op();}catch(e){store.clear();for(const [k,v] of previous)store.set(k,v);throw e;}finally{activeCommitTime=0;}}};}};
  let transactions=Promise.resolve();
  db.runTransaction=fn=>{
    const work=transactions.catch(()=>{}).then(async()=>{
      if(!online||denied)throw Error('fixture unavailable');
      const ops=[];
      const tx={get:r=>r.get({source:'server'}),set:(r,d)=>ops.push(()=>r.set(d)),delete:r=>ops.push(()=>r.delete())};
      const result=await fn(tx),previous=new Map(store);
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
