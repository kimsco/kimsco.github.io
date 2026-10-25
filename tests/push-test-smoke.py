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
    window.permissionCalls=0;window.localNotices=[];window.tokenCalls=0;
    window.Notification={permission:'default',requestPermission:async()=>{permissionCalls++;Notification.permission='granted';return 'granted';}};
    navigator.serviceWorker.getRegistration=async()=>({active:{},showNotification:async(title,options)=>localNotices.push({title,...options})});
    firebase.messaging=()=>({getToken:async options=>{tokenCalls++;if(!options.serviceWorkerRegistration.active)throw Error('missing existing worker');return 'fixture-only-device-token';}});
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>window.copied=value},configurable:true});
   }""")
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350)
   page.locator('#pushTestMenuBtn').click();page.wait_for_timeout(150);assert page.locator('#pushTestOverlay').is_visible()
   assert page.evaluate('permissionCalls')==0 and page.locator('#pushLocalTestBtn').is_disabled()
   page.locator('#pushPermissionBtn').click();assert page.evaluate('permissionCalls')==1
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
   page.locator('#pushTestCloseBtn').click();assert page.locator('#pushTestOverlay').is_hidden()
   page.evaluate("Notification.permission='denied'");page.locator('#pushTestMenuBtn').click()
   assert page.locator('#pushRegisterBtn').is_disabled() and '차단' in page.locator('#pushTestStatus').inner_text()
   page.locator('#pushTestCloseBtn').click();context.close();print('PASS push setup UI',width)
  context=browser.new_context(user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',viewport={'width':390,'height':844})
  context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  page=context.new_page();page.goto('http://127.0.0.1:8201/');page.wait_for_timeout(700)
  page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350);page.locator('#pushTestMenuBtn').click()
  assert '홈 화면에 추가' in page.locator('#pushTestStatus').inner_text() and page.locator('#pushPermissionBtn').is_disabled()
  print('PASS iPhone browser installation guidance');context.close();browser.close()
finally:server.terminate();server.wait()
