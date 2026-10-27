/* Device-only push setup. No Firestore access, credentials or automatic reminders. */
(()=>{
 'use strict';
 const panel=document.getElementById('pushTestOverlay');if(!panel)return;document.body.append(panel);
 const status=document.getElementById('pushTestStatus'),keyInput=document.getElementById('pushVapidKey'),tokenInput=document.getElementById('pushDeviceToken');
 const permissionButton=document.getElementById('pushPermissionBtn'),localButton=document.getElementById('pushLocalTestBtn'),registerButton=document.getElementById('pushRegisterBtn'),copyButton=document.getElementById('pushCopyTokenBtn');
 const checkButton=document.getElementById('pushCheckBtn'),renewButton=document.getElementById('pushRenewBtn');
 const permissionBox=document.getElementById('notificationPermissionBox'),permissionState=document.getElementById('notificationPermissionState'),permissionHint=document.getElementById('notificationPermissionHint');
 const keyName='mf_push_vapid_public_v1';let lastFocus=null,messagingLoad=null,busy=false,background=[],renderedPermission=null;
 try{keyInput.value=localStorage.getItem(keyName)||'';}catch(_){}
 const isiOS=()=>/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const standalone=()=>navigator.standalone===true||matchMedia('(display-mode: standalone)').matches;
 function supported(){
  if(isiOS()&&!standalone())return '아이폰에서는 Safari의 공유 → 홈 화면에 추가 후, 홈 화면의 앱에서 열어주세요. iOS 16.4 이상이 필요합니다.';
  if(!isSecureContext||!('Notification'in window)||!('serviceWorker'in navigator)||!('PushManager'in window))return '이 브라우저에서는 웹 푸시를 사용할 수 없습니다. 최신 iOS의 홈 화면 앱에서 다시 확인해주세요.';
  return '';
 }
 function say(message){status.textContent=message;}
 function updatePermissionBox(){
  const permission='Notification'in window?Notification.permission:'unsupported',granted=permission==='granted';
  if(renderedPermission!==null&&renderedPermission!==permission&&!busy)permissionNotice('');
  renderedPermission=permission;
  permissionState.textContent=granted?'허용됨':'미허용';
  permissionBox.setAttribute('aria-label',granted?'알림 허용. 알림 권한 설정 안내':'알림 미허용. 눌러서 알림 허용');
  permissionBox.setAttribute('aria-busy',String(busy));permissionBox.disabled=busy;
 }
 function permissionNotice(message){permissionHint.textContent=message;permissionHint.hidden=!message;}
 function refresh(){
  updatePermissionBox();
  const unsupported=supported(),granted=!unsupported&&Notification.permission==='granted';
  checkButton.disabled=busy||!granted;renewButton.disabled=busy||!granted;permissionButton.disabled=busy||!!unsupported;localButton.disabled=busy||!granted;registerButton.disabled=busy||!granted;copyButton.disabled=busy||!tokenInput.value;
  if(unsupported)say(unsupported);
  else if(Notification.permission==='denied')say('알림이 차단되어 있습니다. 기기 설정에서 이 앱의 알림을 허용한 뒤 다시 열어주세요.');
  else if(!granted)say('먼저 알림 권한을 허용해주세요. 자동 운동 알림은 아직 보내지 않습니다.');
 }
 function setBusy(value){busy=value;refresh();}
 async function registration(){
  const existing=await navigator.serviceWorker.getRegistration('/');
  if(existing?.active)return existing;
  let timeout;
  try{return await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('앱 업데이트 중입니다. 잠시 뒤 다시 시도해주세요.')),12000);})]);}
  finally{clearTimeout(timeout);}
 }
 function workerHealth(worker){
  return new Promise((resolve,reject)=>{
   const channel=new MessageChannel();
   const timeout=setTimeout(()=>{channel.port1.close();channel.port2.close();reject(Error('수신 코드의 응답을 받지 못했습니다. 앱을 최신 버전으로 다시 연 뒤 확인해주세요.'));},4000);
   channel.port1.onmessage=event=>{clearTimeout(timeout);channel.port1.close();channel.port2.close();if(event.data?.pushReady)resolve(event.data);else reject(Error('푸시 수신 코드가 준비되지 않았습니다.'));};
   try{worker.active.postMessage({type:'TTT_PUSH_HEALTH'},[channel.port2]);}
   catch(_){clearTimeout(timeout);channel.port1.close();channel.port2.close();reject(Error('푸시 수신 코드와 연결하지 못했습니다. 앱을 다시 열어주세요.'));}
  });
 }
 function subscriptionMatches(subscription,key){
  if(!subscription?.options?.applicationServerKey || !validKey(key))return null;
  const bytes=new Uint8Array(subscription.options.applicationServerKey);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'')===key;
 }
 checkButton.addEventListener('click',async()=>{
  if(busy||supported()||Notification.permission!=='granted')return;setBusy(true);say('푸시 수신 연결을 확인하고 있습니다…');
  try{
   const worker=await registration(),health=await workerHealth(worker),subscription=await worker.pushManager.getSubscription();
   if(!subscription){say('알림 권한은 있지만 원격 푸시 구독이 없습니다. 아래에서 공개 키를 입력하고 이 기기 푸시 등록을 눌러주세요.');return;}
   if(subscriptionMatches(subscription,keyInput.value.trim())===false){say('입력한 공개 키와 기기에 등록된 키가 다릅니다. 올바른 프로젝트 키를 확인한 뒤 푸시 연결 다시 만들기를 눌러주세요.');return;}
   if(health.receipt?.receivedAt){
    const when=new Date(health.receipt.receivedAt).toLocaleString();
    say(health.receipt.displayed?'원격 푸시가 기기에 도착했고 알림 표시 요청도 완료됐습니다. 최근 수신: '+when+'. 알림이 보이지 않으면 iOS 집중 모드·알림 요약을 확인해주세요.':'원격 푸시는 도착했지만 알림 표시에 실패했습니다. iOS 알림 설정을 확인해주세요. 최근 수신: '+when);
   }else say('수신 코드와 기기 구독은 정상입니다. 이 버전에서 아직 원격 푸시를 받은 기록은 없습니다. Firebase 프로젝트 rmpj-7ca13에서 현재 토큰으로 전송했는지 확인해주세요.');
  }catch(error){say(error.message||'수신 연결을 확인하지 못했습니다.');}finally{setBusy(false);}
 });
 function validKey(value){
  try{const raw=atob(value.replace(/-/g,'+').replace(/_/g,'/'));return /^[A-Za-z0-9_-]+$/.test(value)&&raw.length===65&&raw.charCodeAt(0)===4;}catch(_){return false;}
 }
 function loadMessaging(){
  if(typeof firebase.messaging==='function')return Promise.resolve();
  if(messagingLoad)return messagingLoad;
  messagingLoad=new Promise((resolve,reject)=>{
   const script=document.createElement('script');script.src='https://www.gstatic.com/firebasejs/13.0.0/firebase-messaging-compat.js';
   const timeout=setTimeout(()=>{script.remove();reject(Error('푸시 연결을 불러오지 못했습니다. 인터넷 연결을 확인해주세요.'));},15000);
   script.onload=()=>{clearTimeout(timeout);resolve();};script.onerror=()=>{clearTimeout(timeout);script.remove();reject(Error('푸시 연결을 불러오지 못했습니다. 인터넷 연결을 확인해주세요.'));};document.head.append(script);
  }).catch(error=>{messagingLoad=null;throw error;});return messagingLoad;
 }
 document.getElementById('pushTestMenuBtn').addEventListener('click',()=>{
  lastFocus=document.activeElement;panel.hidden=false;
  background=[...document.body.children].filter(el=>el!==panel&&!['SCRIPT','STYLE'].includes(el.tagName)).map(el=>[el,el.inert]);background.forEach(([el])=>{el.inert=true;});
  refresh();document.getElementById('pushTestCloseBtn').focus({preventScroll:true});
 });
 function close(){panel.hidden=true;background.forEach(([el,inert])=>{el.inert=inert;});background=[];lastFocus?.focus({preventScroll:true});}
 document.getElementById('pushTestCloseBtn').addEventListener('click',close);
 panel.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();close();}
  if(event.key==='Tab'){
   const controls=[...panel.querySelectorAll('button,input,textarea,summary')].filter(el=>!el.disabled&&el.getClientRects().length);
   const first=controls[0],last=controls.at(-1);
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  }
 });
 async function requestPermission(fromSettings=false){
  if(busy)return;
  const notify=message=>{say(message);if(fromSettings)permissionNotice(message);};
  const unsupported=supported();if(unsupported){notify(unsupported);return;}
  if(Notification.permission==='granted'){notify('알림이 허용되어 있습니다. 끄려면 기기 또는 브라우저 설정에서 이 앱의 알림 권한을 변경해주세요.');return;}
  if(Notification.permission==='denied'){notify('알림이 차단되어 있어 권한 팝업을 다시 띄울 수 없습니다. 기기 또는 브라우저 설정에서 이 앱의 알림을 허용해주세요.');return;}
  permissionNotice('');setBusy(true);
  try{
   // Keep permission request in the original click's user activation; no network/SDK await.
   const permission=await Notification.requestPermission();
   if(permission==='granted')notify('알림을 허용했습니다.');
   else notify(permission==='denied'?'알림이 차단되었습니다. 기기 또는 브라우저 설정에서 허용할 수 있습니다.':'알림은 아직 미허용 상태입니다. 원할 때 다시 요청할 수 있습니다.');
  }catch(_){notify('알림 권한을 요청하지 못했습니다. 홈 화면에 추가한 앱에서 다시 시도해주세요.');}
  finally{setBusy(false);}
 }
 permissionBox.addEventListener('click',()=>requestPermission(true));
 permissionButton.addEventListener('click',()=>requestPermission(false));
 window.addEventListener('focus',refresh);
 window.addEventListener('pageshow',refresh);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
 const settings=document.getElementById('settingsOverlay');
 if(settings)new MutationObserver(updatePermissionBox).observe(settings,{attributes:true,attributeFilter:['class']});
 if(navigator.permissions?.query)navigator.permissions.query({name:'notifications'}).then(state=>state.addEventListener('change',refresh)).catch(()=>{});
 refresh();
 localButton.addEventListener('click',async()=>{
  if(busy||supported()||Notification.permission!=='granted')return;setBusy(true);
  try{const worker=await registration();await worker.showNotification('TTT 테스트 알림',{body:'이 기기에서 알림 표시를 확인했습니다.',icon:'/icons/icon-192.png',tag:'ttt-local-test',data:{url:'/'}});say('기기 테스트 알림을 표시했습니다. 이것은 원격 푸시 수신 테스트와는 별개입니다.');}
  catch(error){say(error.message||'테스트 알림을 표시하지 못했습니다.');}finally{setBusy(false);}
 });
 async function registerDevice(renew=false){
  if(busy||supported()||Notification.permission!=='granted')return;
  const key=keyInput.value.trim();if(!validKey(key)){say('Firebase 웹 푸시 인증서의 공개 VAPID 키를 입력해주세요. 비공개 키는 입력하지 마세요.');keyInput.focus();return;}
  setBusy(true);say('이 기기를 푸시에 연결하고 있습니다…');tokenInput.value='';
  try{
   await loadMessaging();const worker=await registration();await workerHealth(worker);
   const subscription=await worker.pushManager.getSubscription();
   if(!renew && subscriptionMatches(subscription,key)===false)throw Error('입력한 공개 키와 기존 기기 구독의 키가 다릅니다. 올바른 키를 확인한 뒤 푸시 연결 다시 만들기를 눌러주세요.');
   const messaging=firebase.messaging();
   let token=await messaging.getToken({vapidKey:key,serviceWorkerRegistration:worker});
   if(renew){await messaging.deleteToken();token=await messaging.getToken({vapidKey:key,serviceWorkerRegistration:worker});}
   if(!token)throw Error('기기 토큰을 받지 못했습니다. 잠시 뒤 다시 시도해주세요.');
   tokenInput.value=token;try{localStorage.setItem(keyName,key);}catch(_){}
   say('기기 등록 완료. 이 토큰을 복사해 Firebase 프로젝트 rmpj-7ca13의 테스트 메시지에 입력해주세요.'+(renew?' 이전 토큰은 사용하지 마세요.':''));
  }catch(error){say('푸시 등록 실패: '+(error.message||error.code||'공개 키와 인터넷 연결을 확인해주세요.'));}
  finally{setBusy(false);}
 }
 registerButton.addEventListener('click',()=>registerDevice(false));
 renewButton.addEventListener('click',()=>registerDevice(true));
 copyButton.addEventListener('click',async()=>{
  if(!tokenInput.value)return;
  try{await navigator.clipboard.writeText(tokenInput.value);say('기기 토큰을 복사했습니다. Firebase 테스트 메시지의 FCM 등록 토큰 칸에 붙여넣으세요.');}
  catch(_){tokenInput.focus();tokenInput.select();say('토큰을 선택했습니다. 길게 눌러 복사해주세요.');}
 });
})();
