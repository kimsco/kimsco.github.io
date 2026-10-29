"""Home shares settings card language while keeping backgrounds and actions intact."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8223','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   context=browser.new_context(viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8223');page.wait_for_timeout(1500)
   assert page.locator('#homeNormalContent .home-card').count()==4
   assert page.locator('.home-card-label svg').count()==0
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light);page.wait_for_timeout(150)
    styles=page.evaluate('''()=>{
     const cards=[...homeNormalContent.querySelectorAll('.home-card')];
     return {bg:getComputedStyle(document.querySelector('.app')).backgroundColor,image:getComputedStyle(document.querySelector('.app')).backgroundImage,
      cards:cards.map(e=>({bg:getComputedStyle(e).backgroundColor,radius:getComputedStyle(e).borderRadius,border:getComputedStyle(e).borderTopWidth,overflow:e.scrollWidth>e.clientWidth})),
      button:getComputedStyle(document.getElementById('homeDietQuickBtn')).borderRadius};
    }''')
    assert styles['image']=='none',styles
    assert styles['bg']==('rgb(255, 255, 255)' if light else 'rgb(0, 0, 0)'),styles
    assert all(c['bg']==('rgb(255, 255, 255)' if light else 'rgb(28, 28, 29)') and c['radius']=='20px' and c['border']=='0px' and not c['overflow'] for c in styles['cards']),styles
    assert styles['button']=='50%',styles
    page.evaluate("document.querySelector('.app').scrollTop=0");page.screenshot(path=f'/tmp/home-settings-design-{width}-{light}.png')
    page.evaluate("document.querySelector('.app').scrollTop=document.querySelector('.app').scrollHeight");page.wait_for_timeout(150);page.screenshot(path=f'/tmp/home-settings-diet-{width}-{light}.png')
    button=page.locator('#homeDietQuickBtn').bounding_box();assert button['width']==36
    assert button['y']+button['height']<=page.locator('.bottomTab').bounding_box()['y'],button
   page.evaluate("document.querySelector('.app').scrollTop=0")
   page.locator('#homeWeightPill').click();assert page.locator('#homeWeightQuickModal').is_visible();page.evaluate('closeHomeWeightQuickModal()')
   page.locator('#homeDietQuickBtn').click();assert page.locator('#quickAddMealModal').is_visible();page.locator('#quickMealCancel').click()
   assert not errors,errors
   print('PASS home styling, unchanged page backgrounds, responsive cards/icons, weight and meal actions',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
