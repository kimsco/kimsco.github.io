"""Reference header geometry, actions and timer compatibility, using isolated data."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8217','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   context=browser.new_context(viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   context.add_init_script("localStorage.setItem('mf_rest_timer_enabled','1')")
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8217');page.wait_for_timeout(1500)
   def geometry():return page.evaluate('''()=>{
    const r=document.createRange();r.selectNodeContents(document.querySelector('#topTitleText>div'));
    const title=r.getBoundingClientRect(),bell=document.querySelector('#openAnnouncementBtn>svg').getBoundingClientRect(),settings=document.querySelector('#openSettingsBtn>svg').getBoundingClientRect(),bar=document.querySelector('.topBar').getBoundingClientRect();
    return {center:title.x+title.width/2,barCenter:bar.x+bar.width/2,titleRight:title.right,bellLeft:bell.left,bellCenter:bell.x+bell.width/2,rightGap:bar.right-settings.right,spacing:settings.x-bell.x,bellWidth:bell.width,settingsWidth:settings.width,titleY:title.y+title.height/2,bellY:bell.y+bell.height/2};
   }''')
   a=geometry();assert abs(a['center']-a['barCenter'])<1,a
   assert a['titleRight']<=a['bellLeft'],a
   assert a['bellWidth']==20 and a['settingsWidth']==20 and a['spacing']==54,a
   assert a['rightGap']==28,a
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    page.screenshot(path=f'/tmp/header-layout-{width}-{light}.png')
   page.locator('#openAnnouncementBtn').click();page.wait_for_timeout(400);assert page.locator('#announcementModal').is_visible()
   page.locator('#announcementModalCloseBtn').click();page.wait_for_timeout(400)
   page.locator('#openSettingsBtn').click();page.wait_for_timeout(400);assert page.locator('#settingsOverlay').is_visible()
   page.evaluate('closeSettings()');page.wait_for_timeout(400)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(400)
   assert abs(geometry()['center']-a['center'])<1
   page.locator('#recordWeight').fill('60');page.locator('#recordReps').fill('5');page.locator('#recordAdd').click();page.wait_for_timeout(1200)
   assert page.locator('#restTimerDisplay').is_visible();assert page.locator('#restTimerPauseBtn').is_visible()
   page.locator('#restTimerPauseBtn').click();assert page.evaluate('!!restTimerPausedAt')
   page.evaluate('stopRestTimerManually()');page.wait_for_timeout(1000)
   page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(400)
   assert abs(geometry()['center']-a['center'])<1
   assert not errors,errors
   print('PASS centered logo, action geometry, themes, actions, tabs and timer',width,a);context.close()
  browser.close()
finally:server.terminate();server.wait()
