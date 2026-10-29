"""Native edge swipe back, cancellation and unchanged notification wheels."""
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
   page=context.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300);page.evaluate('openSettingsBtn.click()');page.wait_for_timeout(350)
   contact=page.locator('#settingsOverlay a[href^="mailto:"]');assert contact.inner_text()=='문의하기';assert contact.locator('.row-right').count()==0
   page.locator('#notificationPermissionBox').click();page.wait_for_timeout(200);screen=page.locator('#notificationSettingsOverlay');cdp=context.new_cdp_session(page)
   def drag(x,y,dx,dy=0,end='touchEnd'):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for i in range(1,11):
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+dx*i/10,'y':y+dy*i/10}]});page.wait_for_timeout(16)
    moved=screen.bounding_box()['x'];cdp.send('Input.dispatchTouchEvent',{'type':end,'touchPoints':[]});page.wait_for_timeout(350);return moved
   assert drag(10,180,60)>30;assert screen.is_visible();assert abs(screen.bounding_box()['x'])<1
   assert drag(10,180,width*.6,end='touchCancel')>50;assert screen.is_visible();assert abs(screen.bounding_box()['x'])<1
   # Interior horizontal gestures never dismiss; vertical wheel gestures still work.
   drag(width/2,180,width*.35);assert screen.is_visible();assert abs(screen.bounding_box()['x'])<1
   wheel=page.locator('#notificationMinuteWheel');box=wheel.bounding_box();before=wheel.get_attribute('aria-valuenow');drag(box['x']+box['width']/2,box['y']+160,0,-70);assert wheel.get_attribute('aria-valuenow')!=before
   assert drag(10,180,width*.65)>width*.4;assert screen.is_hidden();assert page.locator('#settingsOverlay').is_visible();assert not page.locator('#settingsOverlay').evaluate('e=>e.inert')
   page.locator('#notificationPermissionBox').click();page.wait_for_timeout(200);assert abs(screen.bounding_box()['x'])<1
   page.locator('#notificationSettingsBack').click();assert screen.is_hidden()
   page.locator('#notificationPermissionBox').click();page.wait_for_timeout(150);page.emulate_media(reduced_motion='reduce');drag(10,180,width*.65);assert screen.is_hidden()
   print('PASS short/cancel/interior swipes, native wheels, back, reopen, reduced motion and contact label',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
