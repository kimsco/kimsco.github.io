/* Account-scoped calendar date summary. Hex masks keep one document small and deletions exact. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.MFLastWorkout=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const PARTS=Object.freeze(['가슴','등','어깨','하체','이두','삼두']);
  const DOCUMENT='lastWorkoutDatesV1', WIDTH=92, DAY=86400000;
  const today=(now=Date.now())=>new Date(now+9*3600000).toISOString().slice(0,10);
  function date(key){
    const match=/^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(key||'');
    if(!match) return null;
    const [y,m,d]=match.slice(1).map(Number),ms=Date.UTC(y,m-1,d),dt=new Date(ms);
    if(y<1000 || dt.getUTCFullYear()!==y || dt.getUTCMonth()!==m-1 || dt.getUTCDate()!==d) return null;
    return {year:String(y),ordinal:Math.round((ms-Date.UTC(y,0,1))/DAY),iso:dt.toISOString().slice(0,10),ms};
  }
  function valid(value){
    return value?.schema===1 && Number.isInteger(value.generation) && value.generation>=0 &&
      value.index && !Array.isArray(value.index) && typeof value.index==='object' &&
      Object.entries(value.index).every(([year,parts])=>/^\d{4}$/.test(year) && Number(year)>=1000 &&
        parts && typeof parts==='object' && !Array.isArray(parts) &&
        Object.entries(parts).every(([part,mask])=>PARTS.includes(part) && typeof mask==='string' && /^[0-9a-f]{92}$/.test(mask)));
  }
  const empty=()=>({schema:1,generation:0,index:{},latest:{}});
  function dates(value,asOf=today()){
    const result={},cutoff=date(asOf);
    if(!cutoff || !valid(value)) return result;
    const years=Object.keys(value.index).filter(y=>y<=cutoff.year).sort().reverse();
    for(const part of PARTS){
      for(const year of years){
        const mask=value.index[year][part];if(!mask) continue;
        const limit=year===cutoff.year?cutoff.ordinal:Math.round((Date.UTC(Number(year)+1,0,1)-Date.UTC(Number(year),0,1))/DAY)-1;
        let found=false;
        for(let day=limit;day>=0;day--){
          if(parseInt(mask[Math.floor(day/4)],16)&(1<<(day%4))){
            result[part]=new Date(Date.UTC(Number(year),0,1)+day*DAY).toISOString().slice(0,10);found=true;break;
          }
        }
        if(found) break;
      }
    }
    return result;
  }
  function apply(value,key,data,asOf=today()){
    const parsed=date(key);if(!parsed) return value;
    const result={...value,index:{...value.index}};
    const parts={...(result.index[parsed.year]||{})},position=Math.floor(parsed.ordinal/4),bit=1<<(parsed.ordinal%4);
    for(const part of PARTS){
      const mask=(parts[part]||'0'.repeat(WIDTH)).split('');
      let digit=parseInt(mask[position],16)&~bit;
      if(Array.isArray(data?.muscles) && data.muscles.includes(part)) digit|=bit;
      mask[position]=digit.toString(16);
      const next=mask.join('');
      if(/[^0]/.test(next)) parts[part]=next;else delete parts[part];
    }
    if(Object.keys(parts).length) result.index[parsed.year]=parts;else delete result.index[parsed.year];
    if(asOf!==null){result.latest=dates(result,asOf);result.asOf=asOf;}
    return result;
  }
  function build(docs,asOf=today()){
    let value=empty();
    for(const doc of docs) value=apply(value,doc.id,typeof doc.data==='function'?doc.data():doc.data,null);
    value.latest=dates(value,asOf);value.asOf=asOf;return value;
  }
  function overlay(value,ops,asOf=today()){
    for(const op of Object.values(ops||{})) if(op.collection==='calendar') value=apply(value,op.id,op.data,asOf);
    return dates(value,asOf);
  }
  function elapsed(last,asOf=today()){
    const a=date(last),b=date(asOf);return a && b && a.ms<=b.ms?Math.round((b.ms-a.ms)/DAY):null;
  }
  function createService({db,storage,currentUid,isDeleting=()=>false,onChange=()=>{},now=Date.now}){
    const loaded=new Set(),loading=new Map(),cache=new Map(),serialized=new Map();
    const key=uid=>`mf_account_v2:${uid}:last_workout_dates_v1`;
    const ref=uid=>db.collection('users').doc(uid).collection('meta').doc(DOCUMENT);
    function check(uid){if(!uid || currentUid()!==uid || isDeleting(uid)) throw Error('Account changed or deletion in progress');}
    function cached(uid){
      const raw=storage.getItem(key(uid));
      if(!cache.has(uid) || serialized.get(uid)!==raw){
        let value;try{value=JSON.parse(raw||'null');}catch(_){}
        cache.set(uid,valid(value)?value:null);serialized.set(uid,raw);
      }
      return cache.get(uid);
    }
    function remember(uid,value){
      const previous=cached(uid);
      if(previous && previous.generation>value.generation) return previous;
      const raw=JSON.stringify(value);storage.setItem(key(uid),raw);cache.set(uid,value);serialized.set(uid,raw);
      if(currentUid()===uid) onChange(uid);
      return value;
    }
    async function initialize(uid){
      check(uid);
      // Only an absent/invalid server summary triggers this one-time historical scan.
      const calendar=await db.collection('users').doc(uid).collection('calendar').get({source:'server'});
      check(uid);const value={...build(calendar.docs,today(now())),initializedAt:now()};
      return db.runTransaction(async tx=>{
        const existing=await tx.get(ref(uid));check(uid);
        if(existing.exists && valid(existing.data())) return existing.data();
        tx.set(ref(uid),value);return value;
      });
    }
    function load(uid,{force=false}={}){
      if(loading.has(uid)) return loading.get(uid);
      if(loaded.has(uid) && !force) return Promise.resolve(cached(uid));
      const task=(async()=>{
        check(uid);const snap=await ref(uid).get({source:'server'});check(uid);
        const value=snap.exists && valid(snap.data())?snap.data():await initialize(uid);
        check(uid);const saved=remember(uid,value);loaded.add(uid);return saved;
      })().finally(()=>loading.delete(uid));
      loading.set(uid,task);return task;
    }
    async function send(uid,op){
      await load(uid);check(uid);
      const calendarRef=db.collection('users').doc(uid).collection('calendar').doc(op.id);
      const value=await db.runTransaction(async tx=>{
        const snap=await tx.get(ref(uid));check(uid);
        if(!snap.exists || !valid(snap.data())) {loaded.delete(uid);throw Error('Last workout summary needs initialization');}
        let data=op.data;
        if(data!==null && op.merge){
          const previous=await tx.get(calendarRef);check(uid);data={...(previous.exists?previous.data():{}),...data};
        }
        const next=apply(snap.data(),op.id,data,today(now()));
        next.generation=snap.data().generation+1;next.updatedAt=now();
        check(uid);
        if(data===null) tx.delete(calendarRef);else tx.set(calendarRef,data);
        tx.set(ref(uid),next);return next;
      });
      remember(uid,value);
    }
    return {load,send,cached,view:(uid,ops)=>{
      const value=cached(uid);return {known:!!value,dates:overlay(value||empty(),ops,today(now())),today:today(now())};
    },idle:uid=>Promise.allSettled(loading.has(uid)?[loading.get(uid)]:[])};
  }
  return {PARTS,DOCUMENT,today,date,valid,empty,dates,apply,build,overlay,elapsed,createService};
});
