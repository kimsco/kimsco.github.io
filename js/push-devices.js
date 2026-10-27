/* Account-scoped push device registry. No collection reads or notification sending. */
(function(root){
 'use strict';
 function create({storage,currentUid,allowed,online=()=>true,prepareToken,unsubscribe,saveDevice,removeDevice,hashToken,platform=()=> 'web',now=Date.now,makeId=()=>root.crypto.randomUUID(),lock=(_,fn)=>fn()}){
  const deviceKey='mf_push_device_id_v1',bindingKey='mf_push_binding_v1',refreshMs=7*24*60*60*1000;
  let chain=Promise.resolve(),epoch=0,suspended=false;
  const read=key=>{try{return JSON.parse(storage.getItem(key)||'null');}catch(_){return null;}};
  const ackKey=uid=>`mf_account_v2:${uid}:push_device_ack`;
  function deviceId(){let id=storage.getItem(deviceKey);if(!id){id=makeId();storage.setItem(deviceKey,id);}return id;}
  const writeBinding=value=>value?storage.setItem(bindingKey,JSON.stringify(value)):storage.removeItem(bindingKey);
  const valid=(uid,version)=>!suspended&&version===epoch&&uid===currentUid()&&allowed();
  const enqueue=fn=>{const work=chain.catch(()=>{}).then(()=>lock('mf-push-device-registry',fn));chain=work;return work;};
  async function disconnect(binding){
   if(!binding)return;
   // Persist before network work: another account must rotate this subscription if interrupted.
   writeBinding({...binding,needsRotation:true});
   await unsubscribe();
   if(binding.uid===currentUid())await removeDevice(binding.uid,binding.deviceId);
   storage.removeItem(ackKey(binding.uid));writeBinding(null);
  }
  function sync(){
   const uid=currentUid(),version=epoch;
   return enqueue(async()=>{
    if(suspended||version!==epoch)return false;
    const binding=read(bindingKey);
    if(!uid||!allowed()){
     if(binding && online())await disconnect(binding);
     return false;
    }
    if(!online())return false;
    if(binding&&(binding.uid!==uid||binding.needsRotation))await disconnect(binding);
    if(!valid(uid,version))return false;
    const id=deviceId(),token=await prepareToken();
    if(!token)throw Error('기기 알림 연결을 확인하지 못했습니다.');
    // Record the owner before awaiting a write so an account switch cannot reuse its token.
    writeBinding({uid,deviceId:id,needsRotation:false});
    if(!valid(uid,version))return false;
    const hash=await hashToken(token),previous=read(ackKey(uid));
    if(!valid(uid,version))return false;
    if(previous?.hash===hash&&previous.deviceId===id&&now()-previous.savedAt>=0&&now()-previous.savedAt<refreshMs)return false;
    await saveDevice(uid,id,{token,enabled:true,platform:platform()});
    if(!valid(uid,version))return false;
    storage.setItem(ackKey(uid),JSON.stringify({hash,deviceId:id,savedAt:now()}));return true;
   });
  }
  function accountChanged(){epoch++;suspended=false;return sync();}
  function detach(){
   suspended=true;epoch++;
   return enqueue(async()=>{await disconnect(read(bindingKey));});
  }
  function isRegistered(){const uid=currentUid(),binding=read(bindingKey),ack=uid?read(ackKey(uid)):null;return !!uid&&!suspended&&allowed()&&binding?.uid===uid&&!binding.needsRotation&&ack?.deviceId===binding.deviceId;}
  return {sync,accountChanged,detach,isRegistered};
 }
 const api={create};if(typeof module!=='undefined')module.exports=api;root.MFPushDevices=api;
})(typeof window==='undefined'?globalThis:window);
