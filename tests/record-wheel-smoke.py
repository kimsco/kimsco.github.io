"""Long-press record wheels preserve short-tap and explicit-save behavior; fake Firebase."""
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
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(300)
   page.evaluate("recordWeight.value='50';recordReps.value='7';window.wheelFocuses=0;recordWeight.addEventListener('focus',()=>wheelFocuses++);")
   weight=page.locator('#recordWeight');reps=page.locator('#recordReps');overlay=page.locator('.record-wheel-overlay');wheel=page.locator('.record-wheel-list')
   before=page.evaluate('records.bench.length')
   weight.tap();assert weight.evaluate('el=>el===document.activeElement') and overlay.is_hidden()
   page.evaluate('document.activeElement.blur()');page.wait_for_timeout(50);focus_before=page.evaluate('wheelFocuses')
   r=weight.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2;cdp=c.new_cdp_session(page)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]});page.wait_for_timeout(520)
   assert overlay.is_visible() and page.evaluate('wheelFocuses')==focus_before
   assert overlay.locator('button').count()==0
   sheet=page.locator('.record-wheel-sheet').bounding_box();row=wheel.evaluate("el=>parseFloat(getComputedStyle(el).getPropertyValue('--record-wheel-row'))")
   assert abs(sheet['width']-r['width'])<.1 and abs(sheet['height']-7*row)<.1,(sheet,r,row)
   assert abs(sheet['y']+sheet['height']/2-r['y']-r['height']/2)<.1
   assert sheet['y']>=0 and sheet['y']+sheet['height']<=height
   assert overlay.evaluate('el=>getComputedStyle(el).backgroundColor')=='rgba(0, 0, 0, 0)'
   # Continue with the exact same touch: no release or second touch is required.
   for offset in [10,20,35,50,70]:
    cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y-offset}]});page.wait_for_timeout(30)
   assert int(page.locator('.record-wheel-option[aria-selected="true"]').inner_text())<50
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(100)
   assert overlay.is_visible()
   assert weight.input_value()=='50' and page.evaluate('records.bench.length')==before
   chosen=page.locator('.record-wheel-option[aria-selected="true"]').inner_text()
   page.touchscreen.tap(5,200);assert overlay.is_hidden() and weight.input_value()==chosen
   assert not weight.evaluate('el=>el===document.activeElement')
   assert page.evaluate('records.bench.length')==before
   # Hold and drag with a mouse too; release keeps the wheel open, outside click applies.
   r=reps.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
   page.mouse.move(x,y);page.mouse.down();page.wait_for_timeout(520);assert overlay.is_visible()
   page.mouse.move(x,y-65,steps=5);page.mouse.up();page.wait_for_timeout(100)
   assert overlay.is_visible() and int(page.locator('.record-wheel-option[aria-selected="true"]').inner_text())<7
   wheel.focus();page.keyboard.press('End');assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='1'
   page.keyboard.press('ArrowUp');assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='2'
   page.mouse.click(5,200);assert reps.input_value()=='2'
   for light in [True,False]:
    page.evaluate('(v)=>applyLightMode(v)',light)
    r=weight.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    page.mouse.move(x,y);page.mouse.down();page.wait_for_timeout(520);page.mouse.up();assert overlay.is_visible()
    page.locator('.record-wheel-sheet').evaluate("el=>el.style.setProperty('--wheel-safe-bottom','34px')");page.evaluate("window.dispatchEvent(new Event('resize'))")
    safe=page.locator('.record-wheel-sheet').bounding_box();assert safe['y']+safe['height']<=height-34
    page.locator('.record-wheel-sheet').evaluate("el=>el.style.removeProperty('--wheel-safe-bottom')");page.evaluate("window.dispatchEvent(new Event('resize'))")
    wheel.focus();page.keyboard.press('Home');assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='500'
    wheel.evaluate("el=>el.scrollTop=90*parseFloat(getComputedStyle(el).getPropertyValue('--record-wheel-row'))");page.wait_for_timeout(80)
    page.screenshot(path='/tmp/record-wheel-seven-'+str(width)+'-'+str(light)+'.png')
    page.keyboard.press('Enter');assert overlay.is_hidden() and weight.input_value()=='50'
   # An off-grid direct value remains untouched when aborting with Escape.
   weight.fill('2.5');page.evaluate('document.activeElement.blur()');r=weight.bounding_box();x=r['x']+20;y=r['y']+20
   page.mouse.move(x,y);page.mouse.down();page.wait_for_timeout(520);page.mouse.up();page.keyboard.press('Escape')
   assert overlay.is_hidden() and weight.input_value()=='2.5'
   page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y);page.wait_for_timeout(520);page.mouse.up();assert overlay.is_hidden()
   # Collapsed fields still have seven rows and match the displayed input width.
   page.evaluate("document.getElementById('recordFloatBarTab2').style.transform='scale(.8)'");page.wait_for_timeout(300)
   r=weight.bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
   sheet=page.locator('.record-wheel-sheet').bounding_box();row=wheel.evaluate("el=>parseFloat(getComputedStyle(el).getPropertyValue('--record-wheel-row'))")
   assert abs(sheet['width']-r['width'])<.1 and abs(sheet['height']-7*row)<.1
   page.keyboard.press('Escape');assert weight.input_value()=='2.5'
   page.evaluate("document.getElementById('recordFloatBarTab2').style.transform='scale(1)'");page.wait_for_timeout(300)
   weight.fill('55');page.locator('#recordAdd').click();page.wait_for_timeout(400);assert page.evaluate('records.bench.length')==before+1
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(300)
   page.evaluate("openExerciseDetail('휠 테스트');document.getElementById('acc-weight').value='25'")
   acc=page.locator('#acc-weight');r=acc.bounding_box();page.mouse.move(r['x']+20,r['y']+20);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
   assert overlay.is_visible();wheel.evaluate("el=>el.scrollTop=92*parseFloat(getComputedStyle(el).getPropertyValue('--record-wheel-row'))");page.wait_for_timeout(80)
   page.mouse.click(5,200);assert acc.input_value()=='40' and page.evaluate("accRecordsByExercise['휠 테스트'].length")==0
   print('PASS: same-finger touch/mouse hold-drag, seven rows, no buttons, inline geometry, outside apply, keyboard/escape, short taps and explicit saves')
   c.close()
  b.close()
finally:server.terminate();server.wait()
