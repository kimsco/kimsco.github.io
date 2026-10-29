"""Isolated profile save feedback: entrance, check, hold, repeat and exit."""
import subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8213','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();dialogs=[];page.on('dialog',lambda d:(dialogs.append(d.message),d.dismiss()))
   page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1200);page.evaluate('openMySpec()');page.wait_for_timeout(400)
   page.locator('#specName').fill('토스트 테스트');page.locator('#saveSpecBtn').click();page.wait_for_timeout(650)
   toast=page.locator('.profile-save-toast');assert toast.is_visible();assert toast.inner_text()=='저장했어요';assert toast.get_attribute('role')=='status'
   assert page.evaluate('userSpec.name')=='토스트 테스트';assert page.locator('#mySpecScreen').is_visible();assert not dialogs
   box=toast.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width
   assert toast.evaluate('e=>getComputedStyle(e).pointerEvents')=='none'
   assert toast.locator('path').evaluate('e=>getComputedStyle(e).strokeDashoffset')=='0px'
   page.screenshot(path=f'/tmp/profile-save-toast-{width}.png')
   page.wait_for_timeout(1100);assert toast.is_visible()
   # Another save restarts the existing toast and its lifetime.
   page.locator('#saveSpecBtn').click();page.wait_for_timeout(900);assert toast.count()==1 and toast.is_visible()
   page.wait_for_timeout(1900);assert toast.is_hidden()
   page.evaluate('applyLightMode(true)');page.emulate_media(reduced_motion='reduce');page.locator('#saveSpecBtn').click();page.wait_for_timeout(50)
   assert toast.is_visible();assert toast.locator('.profile-toast-check').evaluate('e=>getComputedStyle(e).animationName')=='none'
   assert toast.locator('path').evaluate('e=>getComputedStyle(e).strokeDashoffset')=='0px'
   print('PASS save feedback, timing, repeat, themes and reduced motion',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
