"""Web startup layout checks; iOS native launch transitions require a real device."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
fixture=(ROOT/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for light in [False,True]:
  c=b.new_context(viewport={'width':390,'height':824},is_mobile=True)
  c.add_init_script("Object.defineProperty(navigator,'standalone',{value:true});Object.defineProperty(screen,'height',{value:844});Object.defineProperty(screen,'width',{value:390});localStorage.setItem('mf_light_mode','"+('1' if light else '0')+"');")
  def route(r):
   r.fulfill(body=fixture if '/firebase-app.js' in r.request.url else '',content_type='application/javascript')
  c.route('https://**/*',route)
  page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8000/',wait_until='domcontentloaded')
  a=page.locator('#bootSplash img').bounding_box()
  assert abs(a['y']+a['height']/2-422)<.1,a
  assert page.locator('meta[name="theme-color"]').get_attribute('content')=='#000000'
  page.set_viewport_size({'width':390,'height':844})
  z=page.locator('#bootSplash img').bounding_box()
  assert abs(a['y']-z['y'])<.1,(a,z)
  page.wait_for_timeout(1200)
  assert page.locator('#bootSplash').count()==0
  assert page.locator('meta[name="theme-color"]').get_attribute('content')==('#ffffff' if light else '#000000')
  assert not errors,errors
  page.goto('http://127.0.0.1:8000/?modeswitch=1',wait_until='domcontentloaded')
  assert not page.locator('#bootSplash').is_visible()
  assert page.locator('meta[name="theme-color"]').get_attribute('content')==('#ffffff' if light else '#000000')
  c.close()
 b.close()
 print('PASS: fixed iOS portrait logo center across viewport resize, dark/light theme handoff and mode-switch bypass (simulated standalone)')
