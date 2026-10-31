"""Mirrored menu background motion and cleanup across routes."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];server=subprocess.Popen(['python','-m','http.server','8231','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width in [320,390,430]:
   c=b.new_context(viewport={'width':width,'height':844});fixture=(root/'tests/firebase-fixture.js').read_text()
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();page.goto('http://127.0.0.1:8231');page.wait_for_timeout(1600)
   page.evaluate('applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(400)
   assert page.locator('#navAboutLabel').is_visible()
   assert page.locator('.app').evaluate('e=>new DOMMatrixReadOnly(getComputedStyle(e).transform).m41')==16
   assert page.locator('.home-mode-motion-layer').evaluate('e=>e.style.transform')=='translateX(16px)'
   page.evaluate('closeNavDrawer()');page.wait_for_timeout(75)
   frame=page.locator('.app').evaluate('e=>({x:new DOMMatrixReadOnly(getComputedStyle(e).transform).m41,opacity:Number(getComputedStyle(e).opacity)})')
   assert 0<frame['x']<16 and 0<frame['opacity']<1,frame
   page.wait_for_timeout(350)
   assert page.locator('.app').evaluate('e=>!e.style.transform&&!e.style.opacity')
   assert page.locator('.topBar').evaluate('e=>!e.style.transform')
   assert page.locator('.home-mode-motion-layer').evaluate('e=>!e.style.transform&&!e.style.opacity')
   # Destination openings must receive a reset background, not inherit a faded app.
   page.evaluate('openNavDrawer()');page.wait_for_timeout(400)
   page.locator('#navTodayRecordsOpen').click();page.wait_for_timeout(350)
   assert page.locator('#todayRecordsOverlay').is_visible()
   assert page.locator('.app').evaluate('e=>!e.style.transform&&!e.style.opacity&&!e.inert')
   print('PASS restored heading, mirrored return motion, synced chrome and destination cleanup',width)
   c.close()
  b.close()
finally:server.terminate();server.wait()
