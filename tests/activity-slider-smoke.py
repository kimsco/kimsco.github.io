"""Continuous pointer movement and magnetic release, using isolated Firebase."""
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
   page=context.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1200);page.evaluate('openMySpec()');page.wait_for_timeout(400)
   track=page.locator('#activitySliderTrack');track.scroll_into_view_if_needed();box=track.bounding_box();x=box['x'];y=box['y']+2;w=box['width']
   ratio=lambda:page.locator('#activitySliderHandle').evaluate('e=>parseFloat(getComputedStyle(e).left)/e.parentElement.clientWidth')
   page.mouse.move(x+w*.5,y);page.mouse.down();page.mouse.move(x+w*.37,y,steps=8);assert abs(ratio()-.37)<.01,ratio()
   assert track.get_attribute('aria-valuenow')=='1'
   page.mouse.up();page.wait_for_timeout(60);mid=ratio();assert .25<mid<.37,mid;page.wait_for_timeout(330);assert abs(ratio()-.25)<.01
   # Native touch follows the finger and does not scroll the sheet.
   cdp=context.new_cdp_session(page);before=page.locator('#mySpecBody').evaluate('e=>e.scrollTop')
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x+w*.25,'y':y}]})
   for i in range(1,9):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+w*(.25+.38*i/8),'y':y}]});page.wait_for_timeout(16)
   assert abs(ratio()-.63)<.01,ratio();assert page.locator('#mySpecBody').evaluate('e=>e.scrollTop')==before
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(380);assert abs(ratio()-.75)<.01
   # Cancel returns to the prior step, then keyboard works in either theme.
   page.mouse.move(x+w*.75,y);page.mouse.down();page.mouse.move(x+w*.1,y);track.dispatch_event('pointercancel',{'pointerId':1});page.mouse.up();page.wait_for_timeout(380);assert abs(ratio()-.75)<.01
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light);track.focus();page.keyboard.press('Home');page.wait_for_timeout(350);assert track.get_attribute('aria-valuenow')=='0';page.keyboard.press('End');page.wait_for_timeout(350);assert track.get_attribute('aria-valuenow')=='4'
   page.emulate_media(reduced_motion='reduce');page.keyboard.press('ArrowLeft');assert track.get_attribute('aria-valuenow')=='3';assert page.locator('#activitySliderHandle').evaluate('e=>getComputedStyle(e).transitionDuration')=='0s'
   print('PASS free mouse/touch drag, magnetic release, cancel, keyboard, themes and reduced motion',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
