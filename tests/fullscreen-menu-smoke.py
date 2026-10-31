"""Full-screen menu appearance, routing, focus, gestures and lifecycle safety."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8227','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width,height in [(320,740),(390,844),(430,932)]:
   context=browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8227');page.wait_for_timeout(1500)
   menu=page.locator('#navDrawerOverlay');panel=page.locator('#navDrawer')
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(55)
    moving=panel.bounding_box();assert moving['x']< -1 and abs(moving['y'])<1,moving
    page.wait_for_timeout(375)
    assert menu.is_visible();box=panel.bounding_box();assert abs(box['x'])<1 and abs(box['y'])<1 and box['width']==width and box['height']==height,box
    assert 'radial-gradient' in panel.evaluate('e=>getComputedStyle(e).backgroundImage')
    assert page.locator('#navMenuTitle').evaluate('e=>getComputedStyle(e).fontSize')=='34px'
    assert page.locator('#navMenuCloseBtn').bounding_box()['width']==44
    assert page.locator('#navDrawer .nav-drawer-item:visible .nav-menu-copy>span:first-child').all_inner_texts()==['3대 PR','1RM 계산기','내 루틴','근육부위','WHO IS TTT FOR?']
    assert page.locator('#navDrawer .nav-v2-icon:visible').count()==0
    assert page.locator('#navDrawer .settings-chevron:visible').count()==5
    assert page.locator('#navDrawer .settings-card').first.evaluate('e=>getComputedStyle(e).borderRadius')=='20px'
    assert page.locator('.app').evaluate("e=>e.inert && e.style.transform==='translateX(16px)' && e.style.opacity==='0'")
    assert panel.evaluate('e=>e.scrollWidth<=e.clientWidth')
    assert menu.evaluate('e=>e===document.activeElement && getComputedStyle(e).outlineStyle==="none"')
    assert not page.locator('#navMenuCloseBtn').evaluate('e=>e.matches(":focus-visible")')
    page.screenshot(path=f'/tmp/fullscreen-menu-{width}-{light}.png')
    page.locator('#navMenuCloseBtn').focus();page.keyboard.press('Shift+Tab');assert page.locator('#navWhoForBtn').evaluate('e=>e===document.activeElement')
    page.keyboard.press('Tab');assert page.locator('#navMenuCloseBtn').evaluate('e=>e===document.activeElement')
    page.keyboard.press('Escape');page.wait_for_timeout(400);assert menu.is_hidden();assert not page.locator('.app').evaluate('e=>e.inert || e.style.transform || e.style.opacity')
   if width==320:
    page.set_viewport_size({'width':width,'height':420});page.evaluate('openNavDrawer()');page.wait_for_timeout(400)
    page.locator('#navMenuBody').evaluate('e=>e.scrollTop=80');assert page.locator('#navMenuBody').evaluate('e=>e.scrollTop>0')
    assert abs(page.locator('#navMenuCloseBtn').bounding_box()['y']-18)<1
    page.locator('#navMenuCloseBtn').click();page.wait_for_timeout(400);page.set_viewport_size({'width':width,'height':height})
   # Every currently available menu destination keeps its route.
   for button,destination,close in [('navThreeSummaryBtn','threeSummaryOverlay','closeThreeSummary'),('navOneRMCalcBtn','oneRMCalcOverlay','closeOneRMCalc'),('navMyRoutineBtn','myRoutineOverlay','closeMyRoutine'),('navMuscleFinderBtn','muscleFinderOverlay','closeMuscleFinder'),('navWhoForBtn','whoForOverlay','closeWhoFor')]:
    page.evaluate('openNavDrawer()');page.wait_for_timeout(390);page.locator('#'+button).click();page.wait_for_timeout(100)
    assert menu.is_hidden();assert page.locator('#'+destination).is_visible(),destination
    assert not page.locator('#'+destination).evaluate('e=>e.inert'),destination
    page.evaluate(('whoForCtaReady=true;' if close=='closeWhoFor' else '')+close+'()');page.wait_for_timeout(450)
   page.evaluate('openNavDrawer();closeNavDrawer();openNavDrawer()');page.wait_for_timeout(430);assert menu.is_visible()
   cdp=context.new_cdp_session(page)
   def swipe(x,y,dx,dy):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for i in range(1,11):
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+dx*i/10,'y':y+dy*i/10}]});page.wait_for_timeout(16)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(400)
   swipe(width/2,90,-50,0);assert menu.is_visible()
   swipe(width/2,90,-200,0);assert menu.is_hidden()
   # Existing left-edge shortcut now opens the full-screen menu from the left.
   swipe(5,250,150,0);assert menu.is_visible();assert abs(panel.bounding_box()['y'])<1
   page.locator('#navMenuCloseBtn').click();page.wait_for_timeout(400);assert menu.is_hidden()
   page.emulate_media(reduced_motion='reduce');page.evaluate('openNavDrawer()');page.wait_for_timeout(60);assert abs(panel.bounding_box()['y'])<1
   page.evaluate('closeNavDrawer()');page.wait_for_timeout(60);assert menu.is_hidden()
   # Mini timers survive menu use, and the full timer X remains a stop control.
   page.evaluate('restTimerEnabled=true;resetRestTimerOnSave()');page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(60)
   assert menu.is_visible() and page.evaluate('restTimerActive')
   page.locator('#navMenuCloseBtn').click();page.wait_for_timeout(60)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(350)
   page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(1100)
   assert menu.is_hidden() and not page.evaluate('restTimerActive')
   assert not errors,errors
   print('PASS full-screen menu, themes, all routes, focus, swipe, rapid reopen and reduced motion',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
