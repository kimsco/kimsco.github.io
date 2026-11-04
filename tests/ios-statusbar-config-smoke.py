"""Status-bar install metadata and viewport layout; native iOS rendering needs a device."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8236','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [393,430]:
   c=b.new_context(viewport={'width':width,'height':852},device_scale_factor=3,is_mobile=True,has_touch=True)
   c.add_init_script("Object.defineProperty(navigator,'standalone',{configurable:true,value:true})")
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8236');page.wait_for_timeout(1800)
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    assert page.locator('meta[name="apple-mobile-web-app-status-bar-style"]').count()==0
    assert page.locator('meta[name="theme-color"]').get_attribute('content')==('#ffffff' if light else '#000000')
    assert 'viewport-fit=cover' in page.locator('meta[name="viewport"]').get_attribute('content')
    for height in [852,650]:
     page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(200)
     assert abs(page.locator('.app').bounding_box()['height']-height)<1
     page.evaluate('window.scrollTo(0,100)');page.wait_for_timeout(50);assert page.evaluate('window.scrollY')==0
    page.set_viewport_size({'width':width,'height':852});page.wait_for_timeout(200)
    page.locator('.app').evaluate('e=>e.scrollTop=100');assert page.locator('.app').evaluate('e=>e.scrollTop>0')
    page.locator('#openSettingsBtn').click();page.wait_for_timeout(350)
    body=page.locator('#settingsOverlay .settings-body');body.evaluate('e=>e.scrollTop=170');assert body.evaluate('e=>e.scrollTop>0')
    assert body.evaluate('e=>getComputedStyle(e).filter')=='none'
    page.evaluate('closeSettings()');page.wait_for_timeout(350)
    assert page.locator('meta[name="apple-mobile-web-app-status-bar-style"]').count()==0
   assert not errors,errors
   print('PASS normal status-bar metadata, theme, viewport sizing, root bounds and nested scrolling',width);c.close()
  b.close()
finally:server.terminate();server.wait()
