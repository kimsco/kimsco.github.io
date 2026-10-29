"""Cold-start mini timer padding, restored offsets and 1s toggle fade."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8225','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8225');page.wait_for_timeout(1600)
   def check_layout():
    geometry=page.evaluate('''()=>{
     const viewport=homeModeViewport.getBoundingClientRect(),normal=homeNormalContent.getBoundingClientRect(),last=document.querySelector('.home-diet-card').getBoundingClientRect();
     return {viewport:viewport.height,normal:normal.height,cache:homeModePanelHeights.normal,last:last.bottom,clip:viewport.bottom,scroll:homeModeApp.scrollTop};
    }''')
    assert abs(geometry['viewport']-geometry['normal'])<1,geometry
    assert geometry['last']<=geometry['clip']+1,geometry
    return geometry
   for paused in [False,True]:
    page.evaluate('paused=>{restTimerEnabled=true;localStorage.setItem("mf_rest_timer_enabled","1");resetRestTimerOnSave();if(paused)toggleRestTimerPause();homeModeApp.scrollTop=180}',paused)
    # Simulate Safari restoring the previous app offset just after page show.
    page.add_init_script("window.addEventListener('pageshow',()=>{const app=document.querySelector('.app');if(app)app.scrollTop=180},{once:true})")
    page.reload();page.wait_for_timeout(1600)
    assert page.locator('#restTimerMiniDisplay').is_visible()
    mini=page.locator('#restTimerMiniDisplay').bounding_box();toggle=page.locator('#homeModeSwitch').bounding_box()
    assert abs(toggle['y']-mini['y']-mini['height']-6)<1,(mini,toggle)
    assert check_layout()['scroll']==0
    page.evaluate('homeModeApp.scrollTop=homeModeApp.scrollHeight');page.wait_for_timeout(100)
    button=page.locator('#homeDietQuickBtn').bounding_box();assert button['y']+button['height']<=page.locator('.bottomTab').bounding_box()['y']
    page.screenshot(path=f'/tmp/home-startup-fixed-{width}-{paused}.png')
    # Padding-only updates remain correct even after startup has settled.
    page.evaluate('stopRestTimerManually()');page.wait_for_timeout(200);check_layout()
    page.evaluate('resetRestTimerOnSave()');page.wait_for_timeout(200);check_layout()
   # The fade starts after 1s, then follows the existing 0.8s transition to .5.
   fade=page.evaluate('''async()=>{
    resetHomeModeFade();await new Promise(r=>setTimeout(r,750));
    const before=getComputedStyle(homeModeSwitch).opacity;
    await new Promise(r=>setTimeout(r,450));const during=getComputedStyle(homeModeSwitch).opacity;
    await new Promise(r=>setTimeout(r,800));return {before:Number(before),during:Number(during),after:Number(getComputedStyle(homeModeSwitch).opacity)};
   }''')
   assert fade['before']==1 and .5<fade['during']<1 and abs(fade['after']-.5)<.01,fade
   # Returning from another app preserves an intentional scroll position.
   page.evaluate("homeModeApp.scrollTop=100;window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))");page.wait_for_timeout(150)
   assert page.evaluate('homeModeApp.scrollTop')==100
   assert not errors,errors
   print('PASS cold-start restored timer, first scroll, full card bounds, padding updates, fade and return scroll',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
