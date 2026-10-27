/* Notification permission UI and automatic signed-in device registration. No sending server. */
(()=>{
 'use strict';
 const box=document.getElementById('notificationPermissionBox'),label=document.getElementById('notificationPermissionState'),hint=document.getElementById('notificationPermissionHint');if(!box)return;
 let busy=false,messagingLoad=null,running=null,lastPushOwner;
 const permission=()=>('Notification'in window?Notification.permission:'unsupported');
 const isiOS=()=>/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const standalone=()=>navigator.standalone===true||matchMedia('(display-mode: standalone)').matches;
 function supported(){
  if(!isiOS())return /Android/.test(navigator.userAgent)?'안드로이드 알림은 준비 중입니다. 현재는 아이폰에서만 알림을 제공합니다.':'현재 알림은 아이폰에서만 제공합니다.';
  if(isiOS()&&!standalone())return '아이폰은 홈 화면에 추가한 앱에서 알림을 허용해주세요. iOS 16.4 이상이 필요합니다.';
  if(!isSecureContext||!('Notification'in window)||!('serviceWorker'in navigator)||!('PushManager'in window))return '이 브라우저는 웹 푸시를 지원하지 않습니다. 최신 브라우저에서 다시 확인해주세요.';
  return '';
 }
 function notice(message=''){hint.textContent=message;hint.hidden=!message;}
 function render(){
  if(!isiOS()){label.textContent='준비 중';box.disabled=busy;box.setAttribute('aria-busy',String(busy));box.setAttribute('aria-label','알림 준비 중. 현재는 아이폰에서만 제공');return;}
  const granted=permission()==='granted';label.textContent=granted?'허용됨':'미허용';
  box.disabled=busy;box.setAttribute('aria-busy',String(busy));box.setAttribute('aria-label',granted?'알림 허용됨. 알림 설정 안내':'알림 미허용. 눌러서 알림 허용');
 }
 function bounded(promise,ms=12000){let timeout;return Promise.race([promise,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('연결이 지연되고 있습니다. 인터넷 연결 후 다시 시도해주세요.')),ms);})]).finally(()=>clearTimeout(timeout));}
 async function registration(){
  const existing=await navigator.serviceWorker.getRegistration('/');return existing?.active?existing:bounded(navigator.serviceWorker.ready);
 }
 function publicKey(){
  const key=window.MF_PUSH_CONFIG?.vapidPublicKey||'';
  try{const raw=atob(key.replace(/-/g,'+').replace(/_/g,'/'));if(/^[A-Za-z0-9_-]+$/.test(key)&&raw.length===65&&raw.charCodeAt(0)===4)return key;}catch(_){}
  throw Error('알림 연결 설정을 준비 중입니다. 잠시 뒤 다시 확인해주세요.');
 }
 function loadMessaging(){
  if(typeof firebase.messaging==='function')return Promise.resolve();
  if(!messagingLoad)messagingLoad=new Promise((resolve,reject)=>{
   const script=document.createElement('script');script.src='https://www.gstatic.com/firebasejs/13.0.0/firebase-messaging-compat.js';
   const timer=setTimeout(()=>{script.remove();reject(Error('알림 연결을 불러오지 못했습니다. 인터넷 연결을 확인해주세요.'));},12000);
   script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=()=>{clearTimeout(timer);script.remove();reject(Error('알림 연결을 불러오지 못했습니다. 인터넷 연결을 확인해주세요.'));};document.head.append(script);
  }).catch(error=>{messagingLoad=null;throw error;});return messagingLoad;
 }
 const reminder=MFWorkoutReminder.create({auth,storage:localStorage,config:window.MF_PUSH_CONFIG||{},getWorker:registration,readActivity:(uid,day)=>window.MFReminderRecords?.read(uid,day),syncRecords:()=>window.MFReminderRecords?.sync(),pending:uid=>window.MFReminderRecords?.pending(uid)});
 const registry=MFPushDevices.create({storage:localStorage,backend:reminder.enabled()?'webpush:'+window.MF_PUSH_CONFIG.reminderApiUrl.replace(/\/$/,''):'firestore',currentUid:()=>auth.currentUser?.uid||null,
  allowed:()=>!supported()&&permission()==='granted'&&!accountDeletionBusy&&!appSync.outbox.isDeleting(auth.currentUser?.uid),online:()=>navigator.onLine,
  lock:(name,fn)=>navigator.locks?navigator.locks.request(name,fn):fn(),
  platform:()=>isiOS()?'ios':/Android/.test(navigator.userAgent)?'android':'web',
  hashToken:async token=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token)))].map(x=>x.toString(16).padStart(2,'0')).join(''),
  prepareToken:async()=>{
   if(reminder.enabled())return reminder.prepareToken();
   const vapidKey=publicKey();await loadMessaging();const worker=await registration(),subscription=await worker.pushManager.getSubscription();
   if(subscription?.options?.applicationServerKey){
    const encoded=btoa(String.fromCharCode(...new Uint8Array(subscription.options.applicationServerKey))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');
    if(encoded!==vapidKey)await bounded(subscription.unsubscribe());
   }
   return bounded(firebase.messaging().getToken({vapidKey,serviceWorkerRegistration:worker}));
  },
  unsubscribe:async()=>{const worker=await registration(),subscription=await worker.pushManager.getSubscription();if(subscription){const removed=await bounded(subscription.unsubscribe());if(!removed)throw Error('이전 알림 연결을 해제하지 못했습니다. 다시 시도해주세요.');}},
  saveDevice:async(uid,id,data)=>{
   if(reminder.enabled())return reminder.register(uid,id,data.token);
   if(auth.currentUser?.uid!==uid||accountDeletionBusy||appSync.outbox.isDeleting(uid))throw Error('계정이 변경되었습니다.');
   await bounded(db.collection('users').doc(uid).collection('pushDevices').doc(id).set({...data,updatedAt:firebase.firestore.FieldValue.serverTimestamp()},{merge:true}));
  },
  removeDevice:async(uid,id,backend)=>{if(auth.currentUser?.uid!==uid)return;if(backend.startsWith('webpush:'))await reminder.remove(uid,id,backend.slice(8));else await bounded(db.collection('users').doc(uid).collection('pushDevices').doc(id).delete());}
 });
 function pushOwner(uid){if(lastPushOwner===uid)return;lastPushOwner=uid;void registration().then(worker=>worker.active?.postMessage({type:'TTT_PUSH_SESSION',uid})).catch(()=>{lastPushOwner=undefined;});}
 function sync(changed=false){
  render();if(changed){reminder.resume();pushOwner(null);}if(running&&!changed)return running;
  const uid=auth.currentUser?.uid||null;
  const task=(changed?registry.accountChanged():registry.sync()).then(()=>{
   if(uid&&auth.currentUser?.uid===uid&&registry.isRegistered()&&permission()==='granted'&&!supported())pushOwner(uid);else pushOwner(null);
   if(isiOS()&&permission()==='granted'&&!auth.currentUser)notice('알림 권한이 허용되어 있습니다. 로그인하면 이 기기의 알림이 자동 연결됩니다.');
  }).catch(error=>{if(isiOS()&&permission()==='granted')notice(error.message||'알림 권한은 허용됐지만 기기 연결을 완료하지 못했습니다. 다시 눌러 재시도해주세요.');}).finally(()=>{if(running===task)running=null;render();});
  void reminder.publish().catch(()=>{});running=task;return task;
 }
 async function diagnostics(){
  const worker=await registration(),subscription=await worker.pushManager.getSubscription();
  const result=await bounded(new Promise(resolve=>{
   const channel=new MessageChannel();channel.port1.onmessage=event=>{channel.port1.close();resolve(event.data);};
   worker.active.postMessage({type:'TTT_PUSH_DIAGNOSTICS'},[channel.port2]);
  }),4000);
  const receipt=result.receipt;
  const received=receipt?new Date(receipt.receivedAt).toLocaleString():'없음';
  const status=!receipt?'아직 수신 기록 없음':receipt.status==='shown'?'표시 요청 성공':receipt.status==='failed'?'표시 실패 ('+receipt.errorName+')':'수신됨, 표시 완료 기록 없음';
  notice('알림 진단 · '+result.worker+' · 기기 구독 '+(subscription?'있음':'없음')+' · 계정 등록 '+(registry.isRegistered()?'완료':'미완료')+' · 최근 수신 '+received+' · '+status);
 }
 window.MFNotifications={forgetAccount:()=>bounded(reminder.forget(),12000).catch(()=>{}),detach:()=>{pushOwner(null);const work=registry.detach();reminder.freeze();return bounded(work,14000).catch(()=>{});}};
 window.addEventListener('mf-reminder-snapshot',()=>void reminder.publish().catch(()=>{}));
 window.addEventListener('mf-reminder-records-changed',()=>void reminder.publish({refresh:true}).catch(()=>{}));
 window.addEventListener('mf-reminder-outbox',()=>void reminder.publish({refresh:true}).catch(()=>{}));
 box.addEventListener('click',async()=>{
  if(busy)return;const unsupported=supported();if(unsupported){notice(unsupported);return;}
  if(permission()==='denied'){notice('알림이 차단되어 팝업을 다시 띄울 수 없습니다. 기기 또는 브라우저 설정에서 이 앱의 알림을 허용해주세요.');return;}
  notice();busy=true;render();
  try{
   // Native prompt must stay inside this click, before any SDK/network work.
   const result=permission()==='granted'?'granted':await Notification.requestPermission();render();
   if(result==='granted'){await sync();if(hint.hidden)await diagnostics().catch(()=>notice('알림 진단에 응답이 없습니다. 앱을 다시 열고 재시도해주세요.'));}
   else notice(result==='denied'?'알림이 차단되었습니다. 기기 설정에서 허용할 수 있습니다.':'알림은 미허용 상태입니다. 원할 때 다시 요청할 수 있습니다.');
  }catch(_){notice('알림 권한을 요청하지 못했습니다. 홈 화면에 추가한 앱에서 다시 시도해주세요.');}
  finally{busy=false;render();}
 });
 const resume=()=>{notice();void sync();};
 navigator.serviceWorker?.addEventListener('controllerchange',()=>{lastPushOwner=undefined;void sync();});
 window.addEventListener('focus',resume);window.addEventListener('pageshow',resume);window.addEventListener('online',resume);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)resume();});
 if(navigator.permissions?.query)navigator.permissions.query({name:'notifications'}).then(state=>state.addEventListener('change',resume)).catch(()=>{});
 const settings=document.getElementById('settingsOverlay');if(settings)new MutationObserver(render).observe(settings,{attributes:true,attributeFilter:['class']});
 auth.onAuthStateChanged(()=>void sync(true));render();
})();
