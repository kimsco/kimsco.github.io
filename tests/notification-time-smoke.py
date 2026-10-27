"""Time picker, permission separation and preference retry using isolated services."""
from pathlib import Path
import json,subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8205','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width in [320,390]:
   context=browser.new_context(user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',viewport={'width':width,'height':844})
   fixture=(root/'tests/firebase-fixture.js').read_text()
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   remote={'minuteOfDay':1320,'offline':False};requests=[]
   def route(r):
    request=r.request;path=request.url.split('reminders.test')[-1]
    if path=='/preferences':
     if remote['offline']:r.fulfill(status=503,body='{}',content_type='application/json');return
     if request.method=='PUT':
      body=json.loads(request.post_data);assert sorted(body)==['minuteOfDay'];remote['minuteOfDay']=body['minuteOfDay'];requests.append(body)
     r.fulfill(body=json.dumps({'minuteOfDay':remote['minuteOfDay']}),content_type='application/json')
    else:r.fulfill(body='{"ok":true}',content_type='application/json')
   context.route('https://reminders.test/**',route)
   context.route('**/js/push-config.js*',lambda r:r.fulfill(body="window.MF_PUSH_CONFIG={reminderApiUrl:'https://reminders.test'};",content_type='application/javascript'))
   context.add_init_script("""(()=>{
    localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');Object.defineProperty(navigator,'standalone',{value:true});
    window.fixturePermissionCalls=0;window.Notification={permission:'default',requestPermission:async()=>{fixturePermissionCalls++;return 'default';}};
    navigator.serviceWorker.getRegistration=async()=>({active:{postMessage:()=>{}},pushManager:{getSubscription:async()=>null}});
   })();""")
   page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
   page.goto('http://127.0.0.1:8205/');page.wait_for_timeout(700)
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(300)
   page.locator('#notificationPermissionBox').click()
   overlay=page.locator('#notificationSettingsOverlay');assert overlay.is_visible()
   assert page.evaluate('fixturePermissionCalls')==0
   assert page.locator('#notificationPeriodWheel').get_attribute('aria-valuetext')=='오후'
   assert page.locator('#notificationHourWheel').get_attribute('aria-valuetext')=='10'
   assert page.locator('#notificationHourWheel').get_attribute('aria-valuenow')=='10'
   assert page.locator('#notificationHourWheel').get_attribute('aria-valuemin')=='1'
   assert page.locator('#notificationHourWheel').get_attribute('aria-valuemax')=='12'
   assert page.locator('#notificationMinuteWheel').get_attribute('aria-valuetext')=='00'
   assert page.locator('#settingsOverlay #notificationPermissionHint').count()==0
   page.locator('#notificationHourWheel').focus();page.keyboard.press('End');page.keyboard.press('ArrowUp')
   page.locator('#notificationMinuteWheel').focus();page.keyboard.press('End')
   page.locator('#notificationSaveBtn').click();page.wait_for_function("document.getElementById('notificationSaveStatus').textContent==='저장했어요.'")
   assert remote['minuteOfDay']==1439 and requests[-1]=={'minuteOfDay':1439}
   assert page.evaluate('fixturePermissionCalls')==0
   page.locator('#notificationMinuteWheel').focus();page.keyboard.press('Home')
   page.locator('#notificationSettingsBack').click();page.locator('#notificationPermissionBox').click()
   assert page.locator('#notificationMinuteWheel').get_attribute('aria-valuetext')=='59'
   page.reload();page.wait_for_timeout(800)
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(250)
   page.locator('#notificationPermissionBox').click();page.wait_for_timeout(100)
   assert page.locator('#notificationHourWheel').get_attribute('aria-valuetext')=='11'
   assert page.locator('#notificationMinuteWheel').get_attribute('aria-valuetext')=='59'
   # Failed remote save remains local and retries without changing the selected draft.
   remote['offline']=True
   page.locator('#notificationHourWheel').focus();page.keyboard.press('End')
   page.locator('#notificationMinuteWheel').focus();page.keyboard.press('Home')
   page.locator('#notificationSaveBtn').click()
   page.wait_for_function("document.getElementById('notificationSaveStatus').textContent.includes('기기에 저장')")
   saved=page.evaluate("JSON.parse(localStorage.getItem('mf_account_v2:alice:notification_time_v1'))")
   assert saved['minuteOfDay']==720 and saved['dirty']
   remote['offline']=False;page.evaluate("window.dispatchEvent(new Event('online'))")
   page.wait_for_function("JSON.parse(localStorage.getItem('mf_account_v2:alice:notification_time_v1')).dirty===false")
   assert remote['minuteOfDay']==720
   # Midnight and a native scroller change are both selectable.
   page.locator('#notificationPeriodWheel').focus();page.keyboard.press('Home')
   page.locator('#notificationSaveBtn').click();page.wait_for_function("JSON.parse(localStorage.getItem('mf_account_v2:alice:notification_time_v1')).minuteOfDay===0")
   page.locator('#notificationMinuteWheel').evaluate('(el)=>{el.scrollTop=5*48;}')
   page.wait_for_function("document.getElementById('notificationMinuteWheel').getAttribute('aria-valuetext')==='05'")
   page.locator('#notificationSaveBtn').click();page.wait_for_function("JSON.parse(localStorage.getItem('mf_account_v2:alice:notification_time_v1')).minuteOfDay===5")
   for light in [False,True]:
    page.evaluate('(light)=>document.documentElement.classList.toggle("light-mode-on",light)',light)
    assert overlay.evaluate('(el)=>el.scrollWidth<=window.innerWidth')
    assert page.locator('#notificationSaveBtn').evaluate('(el)=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}')
    colors=page.locator('#notificationAllowBtn').evaluate('(el)=>({bg:getComputedStyle(el).backgroundColor,fg:getComputedStyle(el).color})')
    assert colors['bg']!=colors['fg'],colors
    if width==390:page.screenshot(path='/tmp/notification-time-'+('light' if light else 'dark')+'.png')
   page.keyboard.press('Escape');assert not overlay.is_visible()
   assert not page.locator('#settingsOverlay').evaluate('(el)=>el.inert')
   assert not errors,errors
   print('PASS time settings navigation, wheel/keyboard, local/server save, retry, reload, themes',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
