/* Web Push registration and a date/boolean-only activity projection. No admin credentials. */
(function(root){
 'use strict';
 const koreaDay=(ms=Date.now())=>new Date(ms+9*3600000).toISOString().slice(0,10);
 function hasRecord(groups,day){
  return groups.some(group=>Object.values(group||{}).some(rows=>Array.isArray(rows)&&rows.some(row=>{
   let date=String(row.date||'');if(/^\d{2}\.\d\d\.\d\d$/.test(date))date='20'+date.replaceAll('.','-');
   return row.deleted!==true&&date===day&&((Number.isFinite(Number(row.reps))&&Number(row.reps)>0)||(Number(row.totalSets)>0&&Number(row.totalReps)>0));
  })));
 }
 function create({auth,storage,config,getWorker,readActivity,syncRecords,pending,fetchFn=(...args)=>root.fetch(...args),now=Date.now,online=()=>root.navigator.onLine}){
  let cachedConfig,loading,publishing,suspended=null,needsFresh=false,rerun=false,retryTimer;
  const enabled=()=>!!config.reminderApiUrl;
  const key=uid=>`mf_account_v2:${uid}:reminder_activity_v1`;
  function check(uid,allowFrozen=false){if(!uid||auth.currentUser?.uid!==uid||(!allowFrozen&&suspended===uid))throw Error('알림 계정이 변경되었습니다.');}
  async function request(path,method,body,uid,allowFrozen=false,baseUrl=config.reminderApiUrl){
   check(uid,allowFrozen);const token=await auth.currentUser.getIdToken();check(uid,allowFrozen);
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
   try{
    const response=await fetchFn(baseUrl.replace(/\/$/,'')+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
    check(uid,allowFrozen);if(!response.ok)throw Error('알림 서버 연결을 완료하지 못했습니다. 잠시 후 다시 시도해주세요.');return response.json();
   }finally{clearTimeout(timer);}
  }
  async function publicConfig(){
   if(cachedConfig)return cachedConfig;
   if(!loading)loading=(async()=>{
    const response=await fetchFn(config.reminderApiUrl.replace(/\/$/,'')+'/config',{signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw Error('알림 서버를 확인하지 못했습니다.');const value=await response.json();
    let bytes;try{bytes=Uint8Array.from(atob(value.publicKey.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));}catch(_){}
    if(!value.ready||value.schema!==1||bytes?.length!==65||bytes[0]!==4)throw Error('알림 연결 설정을 준비 중입니다.');
    cachedConfig={...value,bytes};return cachedConfig;
   })().finally(()=>{loading=null;});return loading;
  }
  async function prepareToken(){
   const uid=auth.currentUser?.uid;check(uid);const settings=await publicConfig(),worker=await getWorker();check(uid);
   let subscription=await worker.pushManager.getSubscription();
   const same=subscription?.options?.applicationServerKey&&Array.from(new Uint8Array(subscription.options.applicationServerKey)).join(',')===Array.from(settings.bytes).join(',');
   if(subscription&&!same){if(!await subscription.unsubscribe())throw Error('이전 알림 연결을 해제하지 못했습니다.');subscription=null;}
   check(uid);subscription ||= await worker.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:settings.bytes});check(uid);
   return JSON.stringify(subscription.toJSON());
  }
  async function publish({refresh=false}={}){
   needsFresh ||= refresh;
   if(!enabled()||!auth.currentUser||!online()||suspended===auth.currentUser.uid)return;
   if(publishing){rerun=true;return publishing;}
   const uid=auth.currentUser.uid;
   publishing=(async()=>{
    check(uid);const day=koreaDay(now());let value=readActivity(uid,day),previous;
    try{previous=JSON.parse(storage.getItem(key(uid))||'null');}catch(_){}
    if(!value?.ready||pending(uid))return;
    if(previous?.day===day&&previous.hasRecord===value.hasRecord&&!!previous.hasLocalRecord===!!value.hasLocalRecord)return;
    if(needsFresh||now()-Date.parse(value.basis)>14*60000){needsFresh=false;if(!await syncRecords())return;check(uid);value=readActivity(uid,day);}
    if(!value?.ready||pending(uid)||koreaDay(now())!==day)return;
    check(uid);let deviceId=storage.getItem('mf_push_device_id_v1');if(!deviceId){deviceId=root.crypto.randomUUID();storage.setItem('mf_push_device_id_v1',deviceId);}
    await request('/activity','POST',{day,hasRecord:value.hasRecord,hasLocalRecord:!!value.hasLocalRecord,deviceId,basis:value.basis},uid);
    check(uid);storage.setItem(key(uid),JSON.stringify({day,hasRecord:value.hasRecord,hasLocalRecord:!!value.hasLocalRecord}));
   })().then(()=>clearTimeout(retryTimer)).catch(error=>{
    if(auth.currentUser?.uid===uid&&suspended!==uid&&online()&&!root.document?.hidden){clearTimeout(retryTimer);retryTimer=setTimeout(()=>void publish().catch(()=>{}),30000);retryTimer.unref?.();}throw error;
   }).finally(()=>{publishing=null;if(rerun){rerun=false;queueMicrotask(()=>void publish().catch(()=>{}));}});return publishing;
  }
  return {enabled,prepareToken,publish,
   register:async(uid,id,token)=>{check(uid);return request('/device','PUT',{id,subscription:JSON.parse(token)},uid);},
   remove:(uid,id,baseUrl)=>request('/device','DELETE',{id},uid,true,baseUrl),
   freeze:()=>{suspended=auth.currentUser?.uid||null;clearTimeout(retryTimer);},
   resume:()=>{suspended=null;},
   forget:async()=>{const uid=auth.currentUser?.uid;if(!uid||!enabled())return;suspended=uid;clearTimeout(retryTimer);await publishing?.catch(()=>{});await request('/account','DELETE',undefined,uid,true);storage.removeItem(key(uid));}
  };
 }
 const api={create,koreaDay,hasRecord};if(typeof module!=='undefined')module.exports=api;root.MFWorkoutReminder=api;
})(typeof window==='undefined'?globalThis:window);
