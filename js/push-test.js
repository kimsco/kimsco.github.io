/* Device-only push setup. No Firestore access, credentials or automatic reminders. */
(()=>{
 'use strict';
 const panel=document.getElementById('pushTestOverlay');if(!panel)return;document.body.append(panel);
 const status=document.getElementById('pushTestStatus'),keyInput=document.getElementById('pushVapidKey'),tokenInput=document.getElementById('pushDeviceToken');
 const permissionButton=document.getElementById('pushPermissionBtn'),localButton=document.getElementById('pushLocalTestBtn'),registerButton=document.getElementById('pushRegisterBtn'),copyButton=document.getElementById('pushCopyTokenBtn');
 const keyName='mf_push_vapid_public_v1';let lastFocus=null,messagingLoad=null,busy=false,background=[];
 try{keyInput.value=localStorage.getItem(keyName)||'';}catch(_){}
 const isiOS=()=>/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const standalone=()=>navigator.standalone===true||matchMedia('(display-mode: standalone)').matches;
 function supported(){
  if(isiOS()&&!standalone())return '아이폰에서는 Safari의 공유 → 홈 화면에 추가 후, 홈 화면의 앱에서 열어주세요. iOS 16.4 이상이 필요합니다.';
  if(!isSecureContext||!('Notification'in window)||!('serviceWorker'in navigator)||!('PushManager'in window))return '이 브라우저에서는 웹 푸시를 사용할 수 없습니다. 최신 iOS의 홈 화면 앱에서 다시 확인해주세요.';
  return '';
 }
 function say(message){status.textContent=message;}
 function refresh(){
  const unsupported=supported(),granted=!unsupported&&Notification.permission==='granted';
  permissionButton.disabled=busy||!!unsupported;localButton.disabled=busy||!granted;registerButton.disabled=busy||!granted;copyButton.disabled=busy||!tokenInput.value;
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
 permissionButton.addEventListener('click',async()=>{
  if(busy||supported())return;setBusy(true);
  try{
   // Call directly from the user's click, before any SDK/network await (iOS requirement).
   const permission=await Notification.requestPermission();
   if(permission==='granted')say('알림 권한을 허용했습니다. 먼저 이 기기에 테스트 알림을 표시할 수 있습니다.');
   else say(permission==='denied'?'알림이 차단되었습니다. 기기 설정에서 허용할 수 있습니다.':'알림 권한을 허용하지 않았습니다. 원할 때 다시 시도해주세요.');
  }catch(_){say('알림 권한을 요청하지 못했습니다. 홈 화면에 추가한 앱에서 다시 시도해주세요.');}
  finally{setBusy(false);}
 });
 localButton.addEventListener('click',async()=>{
  if(busy||supported()||Notification.permission!=='granted')return;setBusy(true);
  try{const worker=await registration();await worker.showNotification('TTT 테스트 알림',{body:'이 기기에서 알림 표시를 확인했습니다.',icon:'/icons/icon-192.png',tag:'ttt-local-test',data:{url:'/'}});say('기기 테스트 알림을 표시했습니다. 이것은 원격 푸시 수신 테스트와는 별개입니다.');}
  catch(error){say(error.message||'테스트 알림을 표시하지 못했습니다.');}finally{setBusy(false);}
 });
 registerButton.addEventListener('click',async()=>{
  if(busy||supported()||Notification.permission!=='granted')return;
  const key=keyInput.value.trim();if(!validKey(key)){say('Firebase 웹 푸시 인증서의 공개 VAPID 키를 입력해주세요. 비공개 키는 입력하지 마세요.');keyInput.focus();return;}
  setBusy(true);say('이 기기를 푸시에 연결하고 있습니다…');
  try{
   await loadMessaging();const worker=await registration();
   const token=await firebase.messaging().getToken({vapidKey:key,serviceWorkerRegistration:worker});
   if(!token)throw Error('기기 토큰을 받지 못했습니다. 잠시 뒤 다시 시도해주세요.');
   tokenInput.value=token;try{localStorage.setItem(keyName,key);}catch(_){}
   say('기기 등록 완료. 토큰을 복사해 Firebase의 테스트 메시지에 입력한 뒤 앱을 닫거나 화면을 잠그고 전송해주세요.');
  }catch(error){say('푸시 등록에 실패했습니다. 공개 키와 인터넷 연결을 확인해주세요. '+(error.code||''));}
  finally{setBusy(false);}
 });
 copyButton.addEventListener('click',async()=>{
  if(!tokenInput.value)return;
  try{await navigator.clipboard.writeText(tokenInput.value);say('기기 토큰을 복사했습니다. Firebase 테스트 메시지의 FCM 등록 토큰 칸에 붙여넣으세요.');}
  catch(_){tokenInput.focus();tokenInput.select();say('토큰을 선택했습니다. 길게 눌러 복사해주세요.');}
 });
})();
