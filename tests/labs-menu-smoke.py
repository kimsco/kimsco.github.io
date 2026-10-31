"""Opt-in control-center tiles in a full-screen menu, persisted preference, original menu and settings navigation."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8228','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8228');page.wait_for_timeout(1600)
   page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(400)
   assert page.locator('#navDrawer').bounding_box()['width']==width
   page.locator('#navMenuCloseBtn').click();page.wait_for_timeout(400)
   page.locator('#openSettingsBtn').click();page.wait_for_timeout(450)
   page.locator('#labsSettingsMenuBtn').click()
   toggle=page.locator('#menuV2Toggle');assert toggle.get_attribute('aria-checked')=='false'
   toggle.click();assert toggle.get_attribute('aria-checked')=='true'
   assert page.evaluate('localStorage.getItem("ttt_menu_v2")')=='true'
   page.locator('#labsSettingsScreen .bw-menu-header-close').click()
   assert page.locator('#settingsOverlay').is_visible()
   page.reload();page.wait_for_timeout(1600)
   assert page.locator('html').evaluate('e=>e.classList.contains("menu-v2-on")')
   # A settings reload may restore settings; close it through its normal function.
   page.evaluate('closeSettings()');page.wait_for_timeout(450)
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(400)
    panel=page.locator('#navDrawer');assert panel.bounding_box()['width']==width
    card=page.locator('#navDrawer .settings-card').first
    group=page.locator('#navDrawer .settings-group').first
    assert abs(card.bounding_box()['width']-group.bounding_box()['width'])<1
    first=page.locator('#navThreeSummaryBtn').bounding_box();second=page.locator('#navOneRMCalcBtn').bounding_box()
    routine=page.locator('#navMyRoutineBtn').bounding_box()
    assert abs(first['y']-second['y'])<1
    assert routine['width']>first['width']*1.9 and routine['height']==60
    assert page.locator('#navMyRoutineBtn').evaluate('e=>getComputedStyle(e).background')==page.locator('#navMuscleFinderBtn').evaluate('e=>getComputedStyle(e).background')
    assert page.locator('#navWhoForBtn .nav-v2-description').count()==0
    assert page.locator('#navThreeSummaryBtn .nav-menu-copy>span').first.evaluate('e=>getComputedStyle(e).fontWeight')=='500'
    assert first['height']==64
    for id in ['navMyRoutineBtn','navMuscleFinderBtn']:
     pill=page.locator('#'+id)
     assert pill.bounding_box()['height']==page.locator('#navWhoForBtn').bounding_box()['height']==60
     assert pill.evaluate('e=>getComputedStyle(e).borderRadius')=='999px'
     assert pill.locator('.nav-v2-description').count()==0
    assert page.locator('#navDrawer .nav-v2-icon:visible').count()==5
    assert card.evaluate('e=>e.scrollWidth<=e.clientWidth')
    assert panel.evaluate('e=>e.scrollWidth<=e.clientWidth')
    title=page.locator('#navMenuTitle').bounding_box();close=page.locator('#navMenuCloseBtn').bounding_box()
    assert title['x']+title['width']<=close['x']+1,(title,close)
    assert page.locator('#navDrawer .nav-drawer-item:visible').count()==5
    assert not page.locator('#navDrawer .settings-item-icon').count()
    page.screenshot(path=f'/tmp/labs-menu-{width}-{light}.png')
    page.locator('#navMenuCloseBtn').click();page.wait_for_timeout(400)
    assert page.locator('#navDrawerOverlay').is_hidden()
   page.locator('#openSettingsBtn').click();page.wait_for_timeout(450)
   page.locator('#labsSettingsMenuBtn').click();toggle.click()
   assert toggle.get_attribute('aria-checked')=='false'
   page.keyboard.press('Escape');assert page.locator('#labsSettingsOverlay').is_hidden()
   page.evaluate('closeSettings()');page.wait_for_timeout(450)
   page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(400)
   assert page.locator('#navDrawer').bounding_box()['width']==width
   assert not errors,errors
   print('PASS labs toggle, persistence, control-center tiles in full-screen themes, X close and original menu',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
