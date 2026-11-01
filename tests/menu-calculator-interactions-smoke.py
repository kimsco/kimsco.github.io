"""Calculator outside taps, distinct edge gestures and stable keyboard geometry."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8233','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   c=b.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8233');page.wait_for_timeout(1600)
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
   expand();page.locator('#weight').fill('75')
   before=tile.bounding_box()
   page.evaluate("window.originalCalculatorViewport=window.visualViewport;Object.defineProperty(window,'visualViewport',{configurable:true,value:{height:440,offsetTop:0}});resizeMenuCalculator();adjustCalculatorKeyboardContent();")
   assert tile.bounding_box()==before,(tile.bounding_box(),before)
   assert page.locator('#menuCalculatorContent').evaluate('e=>!!e.style.maxHeight')
   assert page.locator('#weight').input_value()=='75'
   page.evaluate("Object.defineProperty(window,'visualViewport',{configurable:true,value:window.originalCalculatorViewport});adjustCalculatorKeyboardContent();")
   assert tile.bounding_box()==before
   assert page.locator('#menuCalculatorContent').evaluate('e=>!e.style.maxHeight')
   # Inside taps keep it open; outside taps only collapse the calculator.
   page.locator('#menuCalculatorTitle').evaluate('e=>document.getElementById("menuCalculatorContent").click()');assert expanded()
   page.mouse.click(8,90);page.wait_for_timeout(420)
   assert not expanded() and page.locator('#navDrawerOverlay').is_visible()
   assert page.locator('.bottomTab .tabBtn.active').get_attribute('data-target')=='tab4'
   expand();swipe(5,250,35);assert expanded()
   swipe(5,250,0,120);assert expanded()
   swipe(5,250,160);assert not expanded() and page.locator('#navDrawerOverlay').is_visible()
   expand();swipe(width-5,250,-30);assert expanded()
   swipe(width-5,250,-180)
   assert page.locator('#navDrawerOverlay').is_hidden() and not expanded()
   assert page.locator('.bottomTab .tabBtn.active').get_attribute('data-target')=='tab1'
   assert page.locator('.app').evaluate('e=>!e.inert&&!e.style.opacity&&!e.style.transform')
   assert not errors,errors
   print('PASS outside collapse, left edge collapse, right edge home, cancelled/vertical gestures and keyboard stability',width);c.close()
  b.close()
finally:server.terminate();server.wait()
