/* iOS standalone reads must not depend on another WebKit page's IndexedDB lease. */
(function(root){
  'use strict';
  function isIOSStandalone(nav){
    const ios=/iPad|iPhone|iPod/.test(nav.userAgent||'') || (nav.platform==='MacIntel' && nav.maxTouchPoints>1);
    return ios && nav.standalone===true;
  }
  function configure({db,nav,onStage=()=>{}}){
    if(isIOSStandalone(nav)){
      db.settings({experimentalForceLongPolling:true,experimentalAutoDetectLongPolling:false,experimentalLongPollingOptions:{timeoutSeconds:5}});
      onStage('firestore_direct');
      // Account caches and the durable outbox are maintained separately by MFAppSync.
      return Promise.resolve('memory');
    }
    return db.enablePersistence({synchronizeTabs:true}).then(()=>{
      onStage('firestore_persistent');return 'persistent';
    }).catch(()=>{
      onStage('firestore_memory_fallback');return 'memory';
    });
  }
  function decodeValue(value,timestamp){
    if('nullValue' in value)return null;
    if('stringValue' in value)return value.stringValue;
    if('booleanValue' in value)return value.booleanValue;
    if('integerValue' in value)return Number(value.integerValue);
    if('doubleValue' in value)return value.doubleValue;
    if('timestampValue' in value)return timestamp?timestamp(value.timestampValue):value.timestampValue;
    if('arrayValue' in value)return (value.arrayValue.values||[]).map(x=>decodeValue(x,timestamp));
    if('mapValue' in value)return decodeFields(value.mapValue.fields||{},timestamp);
    if('bytesValue' in value)return value.bytesValue;
    if('referenceValue' in value)return value.referenceValue;
    if('geoPointValue' in value)return value.geoPointValue;
    throw Error('Unsupported Firestore value');
  }
  function decodeFields(fields,timestamp){
    return Object.fromEntries(Object.entries(fields).map(([key,value])=>[key,decodeValue(value,timestamp)]));
  }
  async function readProfile({auth,projectId,owner,fetchFn=root.fetch.bind(root),timestamp,timeoutMs=8000,onStage=()=>{}}){
    const user=auth.currentUser;
    if(!user || user.uid!==owner)throw Error('Account changed');
    onStage('profile_rest_start');
    const controller=new AbortController();let timer;
    try{
      return await Promise.race([
        (async()=>{
          const token=await user.getIdToken();
          onStage('profile_rest_auth_ready');
          if(auth.currentUser?.uid!==owner)throw Error('Account changed');
          if(controller.signal.aborted)throw Error('Profile REST timeout');
          const url='https://firestore.googleapis.com/v1/projects/'+encodeURIComponent(projectId)+'/databases/(default)/documents/users/'+encodeURIComponent(owner)+'/profile/spec';
          const response=await fetchFn(url,{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:controller.signal});
          if(auth.currentUser?.uid!==owner)throw Error('Account changed');
          if(controller.signal.aborted)throw Error('Profile REST timeout');
          onStage('profile_rest_response');
          if(response.status===404){onStage('profile_rest_empty');return {id:'spec',exists:false};}
          if(!response.ok){onStage(response.status===401 || response.status===403?'profile_rest_denied':'profile_rest_http_error');throw Error('Profile read rejected');}
          const document=await response.json();
          if(auth.currentUser?.uid!==owner)throw Error('Account changed');
          if(controller.signal.aborted)throw Error('Profile REST timeout');
          const data=decodeFields(document.fields||{},timestamp);
          onStage('profile_rest_received');return {id:'spec',exists:true,data:()=>data};
        })(),
        new Promise((_,reject)=>{timer=setTimeout(()=>{onStage('profile_rest_timeout');controller.abort();reject(Error('Profile REST timeout'));},timeoutMs);})
      ]);
    }catch(e){onStage('profile_rest_error');throw e;}
    finally{clearTimeout(timer);controller.abort();}
  }
  const api={isIOSStandalone,configure,decodeFields,readProfile};
  if(typeof module!=='undefined')module.exports=api;root.MFFirestoreRuntime=api;
})(typeof window==='undefined'?globalThis:window);
