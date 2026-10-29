"""Profile summary presentation with isolated saves and always-visible calculations."""
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
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1200);page.evaluate('openMySpec()');page.wait_for_timeout(400)
   assert page.locator('.spec-summary-empty').count()==1 and page.locator('.spec-nutrition-card').count()==0
   for key,value in [('Height','175'),('Weight','70'),('Age','28')]:page.locator('#spec'+key).fill(value)
   page.locator('#saveSpecBtn').click();page.wait_for_timeout(100)
   assert page.locator('.spec-nutrition-card h2').inner_text()=='내 하루 권장량'
   assert page.locator('.spec-macro-grid dt').all_text_contents()==['단백질','탄수화물','지방']
   assert page.locator('.spec-macro-grid dd').first.inner_text()=='140g'
   details=page.locator('.spec-calculation-details');assert details.locator('summary').count()==0
   assert details.locator('dl').is_visible()
   assert 'BMR' in details.inner_text() and 'TDEE' in details.inner_text()
   page.locator('.goalBtn[data-goal="cut"]').click();assert details.locator('dl').is_visible()
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light);page.locator('#mySpecBody').evaluate('e=>e.scrollTop=e.scrollHeight');page.wait_for_timeout(350)
    assert page.locator('#mySpecBody').evaluate('e=>e.scrollWidth<=e.clientWidth')
    box=page.locator('.spec-nutrition-card').bounding_box();assert box['x']>=0 and box['x']+box['width']<=width
    page.screenshot(path=f'/tmp/profile-summary-{width}-{light}.png')
   assert not errors,errors
   print('PASS empty state, saved summary, macros, visible calculations, themes and overflow',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
