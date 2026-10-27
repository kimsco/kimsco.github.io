"""Production permission UI/device registry with isolated Firebase/notification mocks only."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8202','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  extension="""
   window.fixturePushToken='fixture-token';window.fixtureTokenCalls=0;
   firebase.messaging=()=>({getToken:async options=>{fixtureTokenCalls++;if(!options.serviceWorkerRegistration.active)throw Error('No active worker');return fixturePushToken+'-'+(localStorage.getItem('fixture_unsubscribes')||'0');}});
  """
  for width in [320,390]:
   context=browser.new_context(user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture+extension if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   context.route('**/js/push-config.js*',lambda r:r.fulfill(body="window.MF_PUSH_CONFIG={vapidPublicKey:btoa(String.fromCharCode(4)+String.fromCharCode(...new Uint8Array(64))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=/g,'')};",content_type='application/javascript'))
   context.add_init_script("""(()=>{
    Object.defineProperty(navigator,'standalone',{value:true,configurable:true});
    localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');
    window.fixturePermissionCalls=0;
    window.Notification={permission:localStorage.getItem('fixture_permission')||'default',requestPermission:async()=>{fixturePermissionCalls++;Notification.permission='granted';localStorage.setItem('fixture_permission','granted');return 'granted';}};
    navigator.serviceWorker.getRegistration=async()=>({active:{postMessage:(message,ports)=>{if(message.type==='TTT_PUSH_DIAGNOSTICS')ports[0].postMessage({worker:'mf-v155',receipt:null});}},pushManager:{getSubscription:async()=>({unsubscribe:async()=>{localStorage.setItem('fixture_unsubscribes',String(Number(localStorage.getItem('fixture_unsubscribes')||0)+1));return true;}})}});
   })();""")
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8202/');page.wait_for_timeout(700)
   assert not errors,errors
   assert page.locator('#pushTestMenuBtn,#pushTestOverlay,#pushDeviceToken,#pushVapidKey').count()==0
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350)
   label=page.locator('#notificationPermissionState');assert label.inner_text()=='미허용'
   assert page.evaluate('fixturePermissionCalls')==0 and page.evaluate('fixtureTokenCalls')==0
   page.locator('#notificationPermissionBox').click()
   assert page.locator('#notificationSettingsOverlay').is_visible()
   assert page.evaluate('fixturePermissionCalls')==0
   assert page.locator('#notificationPeriodWheel').get_attribute('aria-valuetext')=='오후'
   assert page.locator('#notificationHourWheel').get_attribute('aria-valuetext')=='10'
   assert page.locator('#notificationMinuteWheel').get_attribute('aria-valuetext')=='00'
   page.locator('#notificationSaveBtn').click()
   page.wait_for_function("document.getElementById('notificationSaveStatus').textContent.includes('자동 알림은 아직 준비 중')")
   assert page.evaluate('fixturePermissionCalls')==0
   assert page.evaluate("JSON.parse(localStorage.getItem('mf_account_v2:alice:notification_time_v1')).minuteOfDay")==1320
   page.locator('#notificationAllowBtn').click()
   page.wait_for_function("fixture.calls.filter(c=>c.type==='set'&&c.path.includes('/pushDevices/')).length===1")
   assert label.inner_text()=='허용됨' and page.evaluate('fixturePermissionCalls')==1
   assert '알림 진단' not in page.locator('#notificationPermissionHint').inner_text()
   assert page.locator('#notificationPermissionBox').locator('#notificationPermissionHint').count()==0
   page.locator('#notificationSettingsBack').click()
   device_id=page.evaluate("localStorage.getItem('mf_push_device_id_v1')")
   path='users/alice/pushDevices/'+device_id
   saved=page.evaluate('(path)=>fixture.store.get(path)',path)
   assert saved['enabled'] and saved['token']=='fixture-token-0'
   assert page.evaluate("fixture.calls.filter(c=>c.type==='get'&&c.path.includes('/pushDevices/')).length")==0
   page.evaluate("window.dispatchEvent(new Event('focus'));window.dispatchEvent(new Event('pageshow'))");page.wait_for_timeout(150)
   assert page.evaluate("fixture.calls.filter(c=>c.type==='set'&&c.path.includes('/pushDevices/')).length")==1
   assert not page.evaluate("Object.values(localStorage).some(v=>v.includes('fixture-token-0'))")
   # App restart rechecks token but does not read or rewrite an unchanged device.
   page.reload();page.wait_for_timeout(800)
   assert page.evaluate("fixture.calls.filter(c=>c.path?.includes('/pushDevices/')).length")==0
   page.evaluate("fixturePushToken='rotated';window.dispatchEvent(new Event('focus'))")
   page.wait_for_function("fixture.calls.some(c=>c.type==='set'&&c.path.includes('/pushDevices/'))")
   assert page.evaluate('(path)=>fixture.store.get(path).token',path)=='rotated-0'
   # Revoked permission deletes the registration without requesting it again.
   page.evaluate("Notification.permission='denied';window.dispatchEvent(new Event('focus'))")
   page.wait_for_function('(path)=>!fixture.store.has(path)',arg=path)
   assert label.inner_text()=='미허용'
   page.evaluate("Notification.permission='granted';window.dispatchEvent(new Event('focus'))")
   page.wait_for_function('(path)=>fixture.store.has(path)',arg=path)
   # Exercise actual app logout order, while suppressing unrelated account reload in this fixture.
   page.evaluate("handleAuthSession=async()=>{};document.getElementById('logoutConfirm').click()")
   page.wait_for_function('fixture.auth.currentUser===null')
   assert not page.evaluate('(path)=>fixture.store.has(path)',path)
   assert page.evaluate("Number(localStorage.getItem('fixture_unsubscribes'))")>=2
   assert not errors,errors
   print('PASS permission/auto-register/dedupe/rotation/revoke/logout',width);context.close()
  # Existing Android installs are retired without prompting, requesting tokens or reading docs.
  context=browser.new_context(user_agent='Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36',viewport={'width':390,'height':844})
  android_seed="fixture.store.set('users/alice/pushDevices/legacy',{token:'legacy-token',enabled:true,platform:'android'});"
  context.route('https://**/*',lambda r:r.fulfill(body=fixture+extension+android_seed if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  context.add_init_script("""(()=>{
   localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');
   localStorage.setItem('mf_push_binding_v1',JSON.stringify({uid:'alice',deviceId:'legacy',needsRotation:false}));
   localStorage.setItem('mf_account_v2:alice:push_device_ack',JSON.stringify({hash:'legacy',deviceId:'legacy',savedAt:Date.now()}));
   window.fixturePermissionCalls=0;window.Notification={permission:'granted',requestPermission:async()=>{fixturePermissionCalls++;return 'granted';}};
   navigator.serviceWorker.getRegistration=async()=>({active:{postMessage:()=>{}},pushManager:{getSubscription:async()=>({unsubscribe:async()=>{localStorage.setItem('fixture_unsubscribes','1');return true;}})}});
  })();""")
  page=context.new_page();page.goto('http://127.0.0.1:8202/');page.wait_for_timeout(800)
  page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350)
  assert page.locator('#notificationPermissionState').inner_text()=='준비 중'
  page.locator('#notificationPermissionBox').click()
  assert '안드로이드 알림은 준비 중' in page.locator('#notificationPermissionHint').inner_text()
  assert page.evaluate('fixturePermissionCalls')==0 and page.evaluate('fixtureTokenCalls')==0
  assert page.evaluate("fixture.calls.filter(c=>c.type==='delete'&&c.path==='users/alice/pushDevices/legacy').length")==1
  assert not page.evaluate("fixture.store.has('users/alice/pushDevices/legacy')")
  assert page.evaluate("localStorage.getItem('mf_push_binding_v1')") is None
  assert page.evaluate("localStorage.getItem('fixture_unsubscribes')")=='1'
  assert not page.evaluate("fixture.calls.some(c=>c.type==='get'&&c.path.includes('/pushDevices/'))")
  assert page.evaluate('Notification.permission')=='granted'
  print('PASS Android unavailable with legacy subscription/document cleanup');context.close()
  # iPhone browser guidance and guest permission: no token registration without login.
  context=browser.new_context(user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',viewport={'width':390,'height':844})
  context.route('https://**/*',lambda r:r.fulfill(body=fixture+extension if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  context.add_init_script("""(()=>{window.fixturePermissionCalls=0;window.Notification={permission:'default',requestPermission:async()=>{fixturePermissionCalls++;Notification.permission='granted';return 'granted';}};})();""")
  page=context.new_page();page.goto('http://127.0.0.1:8202/');page.wait_for_timeout(700)
  page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350)
  page.locator('#notificationPermissionBox').click()
  assert page.evaluate('fixturePermissionCalls')==0 and '홈 화면에 추가' in page.locator('#notificationPermissionHint').inner_text()
  page.evaluate("Object.defineProperty(navigator,'standalone',{value:true,configurable:true})")
  page.locator('#notificationAllowBtn').click();page.wait_for_timeout(150)
  assert page.locator('#notificationPermissionState').inner_text()=='허용됨'
  assert page.evaluate('fixtureTokenCalls')==0 and '로그인하면' in page.locator('#notificationPermissionHint').inner_text()
  assert not page.evaluate("fixture.calls.some(c=>c.path?.includes('/pushDevices/'))")
  print('PASS iPhone installation guidance and guest permission without registration');context.close()
  browser.close()
finally:server.terminate();server.wait()
