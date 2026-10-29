"""Installation edge-swipe and timestamp-based ten-minute pause expiry."""
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
   page=context.new_page();page.clock.install();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300)
   page.evaluate('openSettingsBtn.click()');page.wait_for_timeout(350);page.locator('#installGuideMenuBtn').click();guide=page.locator('#installGuideOverlay');assert guide.is_visible();assert abs(guide.bounding_box()['x'])<1
   cdp=context.new_cdp_session(page)
   def swipe(dx,end='touchEnd'):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':8,'y':100}]})
    for i in range(1,11):
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':8+dx*i/10,'y':100}]});page.wait_for_timeout(15)
    assert guide.bounding_box()['x']>20
    cdp.send('Input.dispatchTouchEvent',{'type':end,'touchPoints':[]});page.wait_for_timeout(350)
   swipe(55);assert guide.is_visible();assert abs(guide.bounding_box()['x'])<1
   swipe(width*.6,'touchCancel');assert guide.is_visible()
   carousel=page.locator('#installGuideCarouselIphoneSafari');carousel.evaluate('e=>e.scrollLeft=e.clientWidth');page.wait_for_timeout(250);assert carousel.evaluate('e=>e.scrollLeft')>0;assert guide.is_visible()
   swipe(width*.65);assert guide.is_hidden();assert page.locator('#settingsOverlay').is_visible()
   page.locator('#installGuideMenuBtn').click();assert abs(guide.bounding_box()['x'])<1;page.locator('#installGuideOverlay .bw-menu-header-close').click();assert guide.is_hidden()
   page.evaluate('closeSettings()')
   page.evaluate('restTimerEnabled=true;resetRestTimerOnSave();toggleRestTimerPause()');assert page.evaluate('restTimerActive && !!restTimerPausedAt')
   page.clock.fast_forward(599000);assert page.evaluate('restTimerActive')
   page.clock.fast_forward(1100);assert not page.evaluate('restTimerActive');assert page.locator('#restTimerMiniDisplay').is_hidden()
   # Resuming before the deadline cancels expiry. A new pause gets its own full window.
   page.evaluate('resetRestTimerOnSave();toggleRestTimerPause()');page.clock.fast_forward(300000);page.evaluate('toggleRestTimerPause()');page.clock.fast_forward(301000);assert page.evaluate('restTimerActive && !restTimerPausedAt')
   page.evaluate('toggleRestTimerPause()');page.clock.fast_forward(599000);assert page.evaluate('restTimerActive');page.clock.fast_forward(1100);assert not page.evaluate('restTimerActive')
   assert not errors,errors;print('PASS guide swipe/carousel/back and paused timer expiry/resume/new pause',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
