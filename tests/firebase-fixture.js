/* Isolated browser fixture. Never contacts production Firebase or deletes real accounts. */
(() => {
  let commitTime=0,activeCommitTime=0;const store = new Map(); const calls = []; let online = true; let denied = false; let reauthError = false; let deleteError = false;
  class Timestamp {constructor(seconds,nanoseconds){this.ms=nanoseconds===undefined?seconds:seconds*1000+nanoseconds/1e6;this.seconds=Math.floor(this.ms/1000);this.nanoseconds=Math.round((this.ms%1000)*1e6);}toMillis(){return this.ms;}valueOf(){return this.ms;}static fromMillis(ms){return new Timestamp(ms);}}
  class FieldValue {static serverTimestamp(){return new FieldValue();}}
  const docSnap = (path,data) => ({id:path.split('/').at(-1),exists:data!==undefined,ref:ref(path),data:()=>data});
  function ref(path){return {path,id:path.split('/').at(-1),collection:n=>query(path+'/'+n),get:async(options)=>{calls.push({path,type:'get',source:options?.source});if(options?.source==='server'&&(!online||denied))throw Error('fixture unavailable');return docSnap(path,store.get(path));},
    set:async(data,opts)=>{calls.push({path,type:'set'});if(!online||denied)throw Error('fixture unavailable');const resolve=v=>v instanceof FieldValue?Timestamp.fromMillis(activeCommitTime || (commitTime=Math.max(commitTime+1,Date.now()))):Array.isArray(v)?v.map(resolve):v && typeof v==='object' && !(v instanceof Timestamp)?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,resolve(x)])):v;data=resolve(data);store.set(path,opts?.merge?{...store.get(path),...data}:data);},
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
  const auth={currentUser:uid?{uid,email:uid+'@example.test',displayName:uid,getIdToken:async()=> 'fixture-token',reauthenticateWithPopup:async()=>{if(reauthError)throw Error('fixture reauthentication canceled');},delete:async()=>{if(deleteError)throw Error('fixture auth deletion failed');localStorage.removeItem('fixture_uid');auth.currentUser=null;listeners.forEach(fn=>fn(null));}}:null,onAuthStateChanged:fn=>{listeners.push(fn);setTimeout(()=>fn(auth.currentUser),0);},signOut:async()=>{localStorage.removeItem('fixture_uid');auth.currentUser=null;listeners.forEach(fn=>fn(null));}};
  const firestore=()=>db;Object.assign(firestore,{Timestamp,FieldValue,FieldPath:{documentId:()=> '__id__'}});
  const authFn=()=>auth;authFn.GoogleAuthProvider=class {};
  window.firebase={initializeApp:()=>{},auth:authFn,firestore};
  const originalFetch=window.fetch.bind(window),snapshots=new Map();
  const stamp=()=>new Date(commitTime=Math.max(commitTime+1,Date.now())).toISOString();
  const encode=value=>value instanceof Timestamp?{timestampValue:new Date(value.toMillis()).toISOString()}:value===null?{nullValue:null}:typeof value==='boolean'?{booleanValue:value}:typeof value==='string'?{stringValue:value}:typeof value==='number'?{doubleValue:value}:Array.isArray(value)?{arrayValue:{values:value.map(encode)}}:{mapValue:{fields:Object.fromEntries(Object.entries(value).filter(([,v])=>v!==undefined).map(([k,v])=>[k,encode(v)]))}};
  window.fetch=async(url,options)=>{
    if(!String(url).includes('firestore.googleapis.com') || !String(url).endsWith(':runQuery'))return originalFetch(url,options);
    if(window.fixtureQueryGate)await window.fixtureQueryGate;
    if(!online || denied)return new Response('{}',{status:503});
    const match=String(url).match(/projects\/([^/]+)\/databases\/\(default\)\/documents\/users\/([^/:]+):runQuery$/);
    const project=decodeURIComponent(match[1]),owner=decodeURIComponent(match[2]);
    if(auth.currentUser?.uid!==owner)return new Response('{}',{status:403});
    const body=JSON.parse(options.body),q=body.structuredQuery,path='users/'+owner+'/'+q.from[0].collectionId;
    const readTime=body.readTime || stamp();
    if(!snapshots.has(readTime))snapshots.set(readTime,new Map(store));
    const f=q.where?.fieldFilter,cutoff=f?.value.timestampValue;
    const filters=f?[[f.field.fieldPath,'>',Timestamp.fromMillis(Date.parse(cutoff))]]:[];
    const toCursor=v=>v.timestampValue?Date.parse(v.timestampValue):v.referenceValue?.split('/').at(-1);
    const order=q.orderBy.map(x=>x.field.fieldPath),key=(entry,field)=>field==='__name__'?entry[0].split('/').at(-1):entry[1][field]?.toMillis?.() ?? entry[1][field];
    const compare=(entry,values)=>{for(let i=0;i<order.length;i++){const a=key(entry,order[i]),b=values[i];if(a!==b)return a<b?-1:1;}return 0;};
    let entries=[...snapshots.get(readTime)].filter(([name,data])=>name.startsWith(path+'/') && name.split('/').length===path.split('/').length+1 && (!f || data.updatedAt?.toMillis?.()>Date.parse(cutoff)));
    entries.sort((a,b)=>compare(a,order.map(field=>key(b,field))));
    if(q.startAt)entries=entries.filter(entry=>compare(entry,q.startAt.values.map(toCursor))>0);
    entries=entries.slice(0,q.limit);
    calls.push({type:'query',path,rest:true,filters,maximum:q.limit,orders:order,returnedDocuments:entries.length,readTime});
    const prefix='projects/'+project+'/databases/(default)/documents/';
    const result=entries.map(([name,data])=>({document:{name:prefix+name,fields:encode(data).mapValue.fields},readTime}));
    if(!result.length)result.push({readTime});
    return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}});
  };
  window.fixture={changeRecord:(collection,id,data)=>{const old=store.get('users/'+auth.currentUser.uid+'/'+collection+'/'+id)||{};store.set('users/'+auth.currentUser.uid+'/'+collection+'/'+id,{...old,...data,updatedAt:Timestamp.fromMillis(Date.parse(stamp()))});},store,calls,setReauthError:v=>reauthError=v,setDeleteError:v=>deleteError=v,setOnline:v=>online=v,setDenied:v=>denied=v,auth};
})();
