"""Profile acrylic styling and viewport-floating home mode background coupling."""
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
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300)
   base=page.locator('#homeModeSwitch').bounding_box();assert base
   for action in ['openSettingsBtn.click()','closeSettings()','openDietOverlay(document.getElementById("dietTabBtn"))','document.getElementById("dietBackCircleBtn").click()','openNavDrawer()','closeNavDrawer()']:
    samples=page.evaluate('''async ([action,base])=>{
      (0,eval)(action);const samples=[];
      for(let i=0;i<26;i++){
        await new Promise(requestAnimationFrame);
        const app=getComputedStyle(document.querySelector('.app')),layer=getComputedStyle(document.querySelector('.home-mode-motion-layer'));
        samples.push({pill:homeModeSwitch.getBoundingClientRect().left-base,app:new DOMMatrix(app.transform).m41,alpha:Number(app.opacity),layerAlpha:Number(layer.opacity)});
      }return samples;
    }''',[action,base['x']])
    assert all(abs(s['pill']-s['app'])<.3 for s in samples),(action,samples)
    assert all(abs(s['alpha']-s['layerAlpha'])<.03 for s in samples),(action,samples)
    page.wait_for_timeout(450)
   page.evaluate("document.querySelector('.app').scrollTop=120");page.wait_for_timeout(150);assert abs(page.locator('#homeModeSwitch').bounding_box()['y']-base['y'])<.1
   page.evaluate('resetHomeModeFade()');page.wait_for_timeout(3900);assert abs(float(page.locator('#homeModeSwitch').evaluate('e=>getComputedStyle(e).opacity'))-.5)<.01
   page.evaluate('openMySpec()');page.wait_for_timeout(400)
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light);page.wait_for_timeout(250);icon=page.locator('#mySpecScreen .spec-hero-icon');assert 'gradient' in icon.evaluate('e=>getComputedStyle(e).backgroundImage');assert 'blur(16px)' in icon.evaluate('e=>getComputedStyle(e).backdropFilter');assert icon.locator('svg').evaluate('e=>getComputedStyle(e).color')=='rgb(255, 255, 255)';page.screenshot(path=f'/tmp/profile-acrylic-{width}-{light}.png')
   assert not errors,errors;print('PASS settings/diet/drawer frame coupling, scroll, fade and acrylic themes',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
