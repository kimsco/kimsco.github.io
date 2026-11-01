"""Calculator tile morph, shared controls, results, reversal and lifecycle cleanup."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8232','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   c=b.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8232');page.wait_for_timeout(1600)
   page.evaluate('applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(400)
   assert page.locator('#navToolsLabel').is_hidden()
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    button=page.locator('#navOneRMCalcBtn');start=button.bounding_box()
    heading=page.locator('#navMenuTitle').bounding_box()
    routine=page.locator('#navMyRoutineBtn').bounding_box()
    button.click();page.wait_for_timeout(110)
    assert page.locator('#navMenuBody').evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.locator('#navMenuTitle').bounding_box()==heading
    assert page.locator('#navMyRoutineBtn').bounding_box()==routine
    assert page.locator('#menuCalculatorContent').evaluate('e=>Number(getComputedStyle(e).opacity)')>.1
    page.screenshot(path=f'/tmp/menu-calculator-opening-{width}-{light}.png')
    panel=page.locator('#menuCalculator');middle=panel.bounding_box()
    assert middle['width']>start['width'] and middle['height']>start['height'],(start,middle)
    assert page.locator('#navDrawerOverlay').is_visible() and page.locator('#oneRMCalcOverlay').is_hidden()
    page.wait_for_timeout(700)
    final=panel.bounding_box();assert final['width']>start['width']*1.9
    first=page.locator('#navThreeSummaryBtn').bounding_box()
    assert abs(final['y']-first['y'])<1 and abs(final['y']+final['height']-844)<1,final
    assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#menuCalculator")')
    assert page.locator('#weight').count()==1 and page.locator('#oneRMCalcDisclaimer').count()==0
    assert page.locator('#navMenuBody').evaluate('e=>e.inert')
    page.locator('#oneRMLiftSelect').select_option('bench');page.locator('#weight').fill('100');page.locator('#reps').select_option('5');page.locator('#goBtn').click()
    assert page.locator('#tableArea>div').count()==12
    expected=page.evaluate('100*NSCA_TABLE.bench[4]')
    assert f'{expected:.1f}kg' in page.locator('#tableArea>div').first.inner_text()
    page.screenshot(path=f'/tmp/menu-calculator-{width}-{light}.png')
    page.locator('#menuCalculatorBack').click();page.wait_for_timeout(110)
    assert page.locator('#navMenuBody').evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.locator('#navMyRoutineBtn').bounding_box()==routine
    page.wait_for_timeout(510)
    assert panel.is_hidden() and not page.locator('#navMenuBody').evaluate('e=>e.inert')
    assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#oneRMCalcOverlay")')
   # Reverse while opening, then reopen and close the full menu externally.
   button.click();page.wait_for_timeout(90);page.keyboard.press('Escape');page.wait_for_timeout(620)
   assert panel.is_hidden() and page.locator('#navDrawerOverlay').is_visible()
   button.click();page.wait_for_timeout(720);page.evaluate('closeNavDrawer()');page.wait_for_timeout(420)
   assert page.locator('#navDrawerOverlay').is_hidden() and panel.is_hidden()
   assert page.locator('.app').evaluate('e=>!e.inert&&!e.style.transform&&!e.style.opacity')
   page.evaluate('applyMenuV2(false);openNavDrawer()');page.wait_for_timeout(400)
   button.click();page.wait_for_timeout(150)
   assert page.locator('#oneRMCalcOverlay').is_visible() and page.locator('#navDrawerOverlay').is_hidden()
   assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#oneRMCalcOverlay")')
   page.evaluate('closeOneRMCalc();applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(400)
   page.emulate_media(reduced_motion='reduce');button.click();page.wait_for_timeout(50)
   assert panel.evaluate('e=>e.classList.contains("is-ready")')
   assert not errors,errors
   print('PASS tile morph, results, themes, reversal, cleanup, legacy and reduced motion',width);c.close()
  b.close()
finally:server.terminate();server.wait()
