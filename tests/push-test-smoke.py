"""Push setup UI using fake Firebase and notification APIs; no real subscriptions or messages."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8201','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844})
   fixture=(root/'tests/firebase-fixture.js').read_text()
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();page.on('pageerror',lambda e:print('PAGE ERROR',e));page.goto('http://127.0.0.1:8201/');page.wait_for_timeout(700)
   page.evaluate("""()=>{
    window.permissionCalls=0;window.localNotices=[];window.tokenCalls=0;window.deleteCalls=0;window.pushReceipt=null;window.pushSubscription={};
    window.Notification={permission:'default',requestPermission:async()=>{permissionCalls++;Notification.permission='granted';return 'granted';}};
    navigator.serviceWorker.getRegistration=async()=>({active:{postMessage:(message,ports)=>ports[0].postMessage({pushReady:true,workerVersion:'fixture-worker',receipt:pushReceipt})},pushManager:{getSubscription:async()=>pushSubscription},showNotification:async(title,options)=>localNotices.push({title,...options})});
    firebase.messaging=()=>({getToken:async options=>{tokenCalls++;if(!options.serviceWorkerRegistration.active)throw Error('missing existing worker');return deleteCalls?'fixture-new-device-token':'fixture-only-device-token';},deleteToken:async()=>{deleteCalls++;return true;}});
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>window.copied=value},configurable:true});
   }""")
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350)
   box=page.locator('#notificationPermissionBox');label=page.locator('#notificationPermissionState')
   assert label.inner_text()=='미허용' and page.evaluate('permissionCalls')==0
   page.evaluate('()=>{window.originalPermissionRequest=Notification.requestPermission;}')
   box.click();page.wait_for_timeout(100);assert label.inner_text()=='허용됨' and page.evaluate('permissionCalls')==1
   assert page.evaluate('tokenCalls')==0
   box.click();assert page.evaluate('permissionCalls')==1 and '설정' in page.locator('#notificationPermissionHint').inner_text()
   page.evaluate("Notification.permission='denied';window.dispatchEvent(new Event('focus'))")
   assert label.inner_text()=='미허용'
   box.click();assert page.evaluate('permissionCalls')==1 and '차단' in page.locator('#notificationPermissionHint').inner_text()
   page.evaluate("()=>{Notification.permission='default';window.dispatchEvent(new Event('pageshow'));Notification.requestPermission=()=>{permissionCalls++;return new Promise(resolve=>{window.finishPermission=()=>resolve('default')});};}")
   box.click();assert box.is_disabled()
   page.evaluate('finishPermission()');assert label.inner_text()=='미허용' and box.is_enabled()
   # Reset the permission stub before exercising the existing test screen too.
   page.evaluate('permissionCalls=0;Notification.requestPermission=originalPermissionRequest;window.dispatchEvent(new Event("focus"))')
   page.locator('#pushTestMenuBtn').click();page.wait_for_timeout(150);assert page.locator('#pushTestOverlay').is_visible()
   assert page.evaluate('permissionCalls')==0 and page.locator('#pushLocalTestBtn').is_disabled()
   page.locator('#pushPermissionBtn').click();assert page.evaluate('permissionCalls')==1 and label.inner_text()=='허용됨'
   page.locator('#pushLocalTestBtn').click();page.wait_for_timeout(80)
   assert page.evaluate('localNotices.length')==1 and '원격 푸시 수신 테스트와는 별개' in page.locator('#pushTestStatus').inner_text()
   page.locator('#pushTestOverlay summary').click();page.locator('#pushRegisterBtn').click()
   assert page.evaluate('tokenCalls')==0 and '공개 VAPID 키' in page.locator('#pushTestStatus').inner_text()
   key=page.evaluate("btoa(String.fromCharCode(4)+String.fromCharCode(...new Uint8Array(64))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=/g,'')")
   page.locator('#pushVapidKey').fill(key);page.locator('#pushRegisterBtn').click();page.wait_for_timeout(100)
   assert page.locator('#pushDeviceToken').input_value()=='fixture-only-device-token'
   page.locator('#pushCopyTokenBtn').click();assert page.evaluate('copied')=='fixture-only-device-token'
   assert page.evaluate("localStorage.getItem('mf_push_vapid_public_v1')")==key
   assert not page.evaluate("Object.values(localStorage).some(v=>v.includes('fixture-only-device-token'))")
   page.locator('#pushCheckBtn').click();page.wait_for_timeout(100)
   assert '아직 원격 푸시를 받은 기록은 없습니다' in page.locator('#pushTestStatus').inner_text()
   page.evaluate('pushReceipt={receivedAt:Date.now(),displayed:true}')
   page.locator('#pushCheckBtn').click();page.wait_for_timeout(100)
   assert '도착했고' in page.locator('#pushTestStatus').inner_text()
   page.evaluate('pushReceipt={receivedAt:Date.now(),displayed:false}')
   page.locator('#pushCheckBtn').click();page.wait_for_timeout(100)
   assert '표시에 실패' in page.locator('#pushTestStatus').inner_text()
   page.evaluate('pushSubscription=null');page.locator('#pushCheckBtn').click();page.wait_for_timeout(100)
   assert '구독이 없습니다' in page.locator('#pushTestStatus').inner_text()
   page.evaluate("pushSubscription={options:{applicationServerKey:new Uint8Array([4,...Array(64).fill(1)]).buffer}}")
   page.locator('#pushRegisterBtn').click();page.wait_for_timeout(100)
   assert '키가 다릅니다' in page.locator('#pushTestStatus').inner_text() and page.locator('#pushDeviceToken').input_value()==''
   page.evaluate('pushSubscription={}')
   page.locator('#pushRenewBtn').click();page.wait_for_timeout(100)
   assert page.evaluate('deleteCalls')==1 and page.locator('#pushDeviceToken').input_value()=='fixture-new-device-token'

   page.locator('#pushTestCloseBtn').click();assert page.locator('#pushTestOverlay').is_hidden()
   page.evaluate("Notification.permission='denied'");page.locator('#pushTestMenuBtn').click()
   assert page.locator('#pushRegisterBtn').is_disabled() and '차단' in page.locator('#pushTestStatus').inner_text()
   page.locator('#pushTestCloseBtn').click();context.close();print('PASS push setup UI',width)
  context=browser.new_context(user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',viewport={'width':390,'height':844})
  context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  page=context.new_page();page.goto('http://127.0.0.1:8201/');page.wait_for_timeout(700)
  page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350);page.locator('#pushTestMenuBtn').click()
  assert '홈 화면에 추가' in page.locator('#pushTestStatus').inner_text() and page.locator('#pushPermissionBtn').is_disabled()
  page.evaluate("()=>{window.permissionCalls=0;window.Notification={permission:'default',requestPermission:async()=>{permissionCalls++;Notification.permission='granted';return 'granted';}};}")
  page.locator('#pushTestCloseBtn').click();page.locator('#notificationPermissionBox').click()
  assert page.evaluate('permissionCalls')==0 and '홈 화면에 추가' in page.locator('#notificationPermissionHint').inner_text()
  page.evaluate("Object.defineProperty(navigator,'standalone',{value:true,configurable:true});window.dispatchEvent(new Event('focus'))")
  page.locator('#notificationPermissionBox').click();page.wait_for_timeout(100)
  assert page.locator('#notificationPermissionState').inner_text()=='허용됨' and page.evaluate('permissionCalls')==1
  print('PASS iPhone installation guidance and standalone permission request');context.close();browser.close()
finally:server.terminate();server.wait()
