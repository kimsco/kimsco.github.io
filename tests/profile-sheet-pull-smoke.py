"""Isolated native touch checks for profile sheet scrolling and pull dismissal."""
import subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
s=subprocess.Popen(['python','-m','http.server','8213','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);f=(root/'tests/firebase-fixture.js').read_text()
  for w in [320,390]:
   c=b.new_context(viewport={'width':w,'height':844},is_mobile=True,has_touch=True);c.route('https://**/*',lambda r:r.fulfill(body=f if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'));page=c.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1200);page.evaluate('openMySpec()');page.wait_for_timeout(500);cdp=c.new_cdp_session(page)
   def swipe(y,dy):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':w/2,'y':y}]})
    for i in range(1,13):
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':w/2,'y':y+dy*i/12}]});page.wait_for_timeout(18)
    return page.locator('#mySpecScreen').bounding_box()['y']
   def release():cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(500)
   top=page.locator('#mySpecScreen').bounding_box()['y'];assert top<70;assert page.locator('#mySpecSheetHandle').count()==0
   # Upward swipe scrolls content normally.
   swipe(430,-220);release();assert page.locator('#mySpecBody').evaluate('e=>e.scrollTop')>30
   # A gesture started within content remains scrolling, even when it reaches the top.
   page.locator('#mySpecBody').evaluate('e=>e.scrollTop=40');page.wait_for_timeout(250);during=swipe(240,150);assert abs(during-top)<2;release()
   page.locator('#mySpecBody').evaluate('e=>e.scrollTop=0');page.wait_for_timeout(300)
   during=swipe(240,70);assert during>top+30,(top,during);release();assert page.locator('#mySpecScreen').is_visible();assert abs(page.locator('#mySpecScreen').bounding_box()['y']-top)<2
   during=swipe(240,190);assert during>top+100;release();assert page.locator('#mySpecScreen').is_hidden()
   page.evaluate('openMySpec()');page.wait_for_timeout(500);assert page.locator('#mySpecScreen').is_visible();assert abs(page.locator('#mySpecScreen').bounding_box()['y']-top)<2
   page.screenshot(path=f'/tmp/profile-pull-{w}.png');page.locator('#mySpecScreen .spec-close-btn').click();page.wait_for_timeout(400);assert page.locator('#mySpecScreen').is_hidden();print('PASS native scrolling, top arrival, short pull, dismiss, reopen and X',w);c.close()
finally:s.terminate();s.wait()
