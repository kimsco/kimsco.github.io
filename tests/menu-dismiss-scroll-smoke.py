"""Menu edge dismissal preserves the current tab and scroll, including with an expanded card."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8240','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   c=b.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8240');page.wait_for_timeout(1600)
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(400)
   page.evaluate('applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(400)
   tile=page.locator('#navOneRMCalcBtn')
   def expand():
    tile.click();page.wait_for_timeout(500);assert tile.evaluate('e=>e.classList.contains("calculator-expanded")')
   def expanded():return tile.evaluate('e=>e.classList.contains("calculator-expanded")')
   cdp=c.new_cdp_session(page)
   def swipe(x,y,dx,dy=0):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for i in range(1,11):
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+dx*i/10,'y':y+dy*i/10}]});page.wait_for_timeout(16)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(520)
   # Return to the same tab, both from the plain menu and from an expanded card.
   swipe(width-5,250,-180)
   assert page.locator('#navDrawerOverlay').is_hidden()
   assert page.locator('.bottomTab .tabBtn.active').get_attribute('data-target')=='tab4'
   app=page.locator('.app')
   for target in ['tab2','tab3','tab4','tab1']:
    page.locator('.bottomTab .tabBtn[data-target="'+target+'"]').click();page.wait_for_timeout(450)
    if target=='tab1':
     app.evaluate('e=>e.scrollTop=220');page.wait_for_timeout(100)
     assert app.evaluate('e=>e.scrollTop')>0
    saved=page.evaluate("[...document.querySelectorAll('.app,#homeSeriousModeScreen,#exerciseScreen,#acc-records,#tab2 .folderContent.active')].map(e=>e.scrollTop)")
    for calculator in [False,True]:
     page.evaluate('openNavDrawer()');page.wait_for_timeout(420)
     if calculator: expand()
     swipe(width-5,250,-180)
     assert page.locator('#navDrawerOverlay').is_hidden() and not expanded()
     assert page.locator('.bottomTab .tabBtn.active').get_attribute('data-target')==target
     assert page.evaluate("[...document.querySelectorAll('.app,#homeSeriousModeScreen,#exerciseScreen,#acc-records,#tab2 .folderContent.active')].map(e=>e.scrollTop)")==saved
     assert app.evaluate('e=>!e.inert&&!e.style.opacity&&!e.style.transform')
   # Explicit home re-tap should retain its intentional scroll-to-top behavior.
   page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(500)
   assert app.evaluate('e=>e.scrollTop')==0
   assert not errors,errors
   print('PASS menu edge dismissal preserves the current tab and scroll with/without card, other-tab return and explicit home re-tap',width);c.close()
  b.close()
finally:server.terminate();server.wait()
