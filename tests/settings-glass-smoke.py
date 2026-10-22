"""Settings-only glass feedback and unchanged setting actions, with fake Firebase."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8198','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width,height in [(320,740),(390,844)]:
   c=b.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
   fixture=(root/'tests/firebase-fixture.js').read_text()
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();page.goto('http://127.0.0.1:8198/');page.wait_for_timeout(700)
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(400)
   assert page.locator('.settings-glass-toggle').count()==7
   assert not page.locator('#calendarToggle').evaluate("el=>el.classList.contains('settings-glass-toggle')")
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light)
    toggle=page.locator('#restTimerToggle');toggle.scroll_into_view_if_needed();page.wait_for_timeout(400)
    before=toggle.evaluate("el=>({active:el.classList.contains('active'),rect:el.closest('.settings-item').getBoundingClientRect().toJSON()})")
    r=toggle.bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down();page.wait_for_timeout(150)
    assert toggle.evaluate("el=>el.classList.contains('glass-pressed')")
    assert toggle.evaluate("el=>el.closest('.settings-item').getBoundingClientRect().toJSON()")==before['rect']
    page.screenshot(path='/tmp/settings-glass-'+str(width)+'-'+str(light)+'-pressed.png')
    page.mouse.up();page.wait_for_timeout(750)
    assert toggle.evaluate("el=>el.classList.contains('active')")!=before['active']
    assert not toggle.evaluate("el=>el.classList.contains('glass-pressed')||el.classList.contains('glass-settling')")
    assert toggle.get_attribute('aria-checked')==str(not before['active']).lower()
    assert toggle.evaluate("el=>el.closest('.settings-item').getBoundingClientRect().toJSON()")==before['rect']
    for i in range(6):toggle.evaluate('el=>el.click()')
    page.wait_for_timeout(750)
    assert toggle.evaluate("el=>el.classList.contains('active')")!=before['active']
    toggle.focus();page.keyboard.press('Space');page.wait_for_timeout(750)
    assert toggle.evaluate("el=>el.classList.contains('active')")==before['active']
    page.emulate_media(reduced_motion='reduce');toggle.evaluate('el=>el.click()');page.wait_for_timeout(50)
    assert toggle.evaluate("el=>getComputedStyle(el,'::after').transitionDuration")=='0s'
    page.emulate_media(reduced_motion='no-preference');page.wait_for_timeout(700)
    page.screenshot(path='/tmp/settings-glass-'+str(width)+'-'+str(light)+'.png')
   print('PASS settings glass',width,'press/release, layout stability, rapid clicks, keyboard, aria, reduced motion and both themes')
   c.close()
  b.close()
finally:server.terminate();server.wait()
