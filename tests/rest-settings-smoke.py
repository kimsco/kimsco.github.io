"""Dedicated stopwatch settings, retained preference and edge navigation."""
import subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8213','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300);page.evaluate('openSettingsBtn.click()');page.wait_for_timeout(350)
   assert page.locator('#settingsOverlay #restTimerToggle').count()==0;assert page.locator('#restSettingsMenuBtn .settings-chevron').count()==1
   page.locator('#restSettingsMenuBtn').click();overlay=page.locator('#restSettingsOverlay');assert overlay.is_visible();toggle=page.locator('#restTimerToggle');assert toggle.is_visible()
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light);toggle.click();active=toggle.evaluate('e=>e.classList.contains("active")');assert page.evaluate('restTimerEnabled')==active;assert page.evaluate('localStorage.getItem("mf_rest_timer_enabled")')==('1' if active else '0');assert overlay.evaluate('e=>e.scrollWidth<=innerWidth');assert '10분' in overlay.inner_text() and '30분' in overlay.inner_text();page.screenshot(path=f'/tmp/rest-settings-{width}-{light}.png')
   toggle.click();assert page.evaluate('restTimerEnabled');page.locator('#restSettingsOverlay .bw-menu-header-close').click();assert overlay.is_hidden();assert page.locator('#settingsOverlay').is_visible()
   page.locator('#restSettingsMenuBtn').click();cdp=context.new_cdp_session(page);cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':8,'y':150}]})
   for i in range(1,11):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':8+width*.65*i/10,'y':150}]});page.wait_for_timeout(16)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(350);assert overlay.is_hidden();assert page.locator('#settingsOverlay').is_visible()
   page.evaluate('closeSettings();resetRestTimerOnSave()');assert page.evaluate('restTimerActive')
   page.reload();page.wait_for_timeout(1300);assert page.evaluate('restTimerEnabled && restTimerActive');page.evaluate('openSettingsBtn.click()');page.wait_for_timeout(350);page.locator('#restSettingsMenuBtn').click();assert page.locator('#restTimerToggle').evaluate('e=>e.classList.contains("active")');page.locator('#restTimerToggle').click();assert not page.evaluate('restTimerActive');assert not errors,errors
   print('PASS rest settings layout, themes, preference, back/swipe, reload and stopping',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
