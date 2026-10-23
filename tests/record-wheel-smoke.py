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
   page.evaluate("recordWeight.value='2.5';recordReps.value='7';window.wheelFocuses=0;recordWeight.addEventListener('focus',()=>wheelFocuses++);")
   weight=page.locator('#recordWeight');reps=page.locator('#recordReps');overlay=page.locator('.record-wheel-overlay')
   before=page.evaluate('records.bench.length')
   # A short tap preserves the keyboard and decimal input path.
   weight.tap();assert weight.evaluate('el=>el===document.activeElement')
   assert overlay.is_hidden();weight.fill('2.5');page.evaluate('document.activeElement.blur()');page.wait_for_timeout(50)
   focus_before=page.evaluate('wheelFocuses')
   # Real touchscreen hold must not focus the input or open a keyboard first.
   r=weight.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2;cdp=c.new_cdp_session(page)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]});page.wait_for_timeout(520)
   assert overlay.is_visible() and page.evaluate('wheelFocuses')==focus_before
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
   assert weight.input_value()=='2.5'
   assert page.locator('.record-wheel-option').count()==101
   assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='5'
   page.locator('.record-wheel-list').evaluate('el=>el.scrollTop=11*44');page.wait_for_timeout(100)
   assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='55'
   page.locator('[data-wheel-confirm]').click();assert weight.input_value()=='55'
   assert overlay.is_hidden() and page.evaluate('records.bench.length')==before
   assert not weight.evaluate('el=>el===document.activeElement')
   # Mouse hold, one-rep steps, keyboard selection and confirmation.
   r=reps.bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+22);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
   assert overlay.is_visible() and page.locator('.record-wheel-option').count()==60
   wheel=page.locator('.record-wheel-list');wheel.focus();page.keyboard.press('ArrowDown')
   assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='8'
   page.locator('[data-wheel-confirm]').click();assert reps.input_value()=='8'
   # Cancel retains off-grid decimal values and does not save a record.
   weight.fill('2.5');page.evaluate('document.activeElement.blur()');r=weight.bounding_box();page.mouse.move(r['x']+20,r['y']+20);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
   wheel.evaluate('el=>el.scrollTop=440');page.wait_for_timeout(80);page.keyboard.press('Escape')
   assert overlay.is_hidden() and weight.input_value()=='2.5' and page.evaluate('records.bench.length')==before
   # Moving before the threshold cancels the long press.
   page.mouse.move(r['x']+20,r['y']+20);page.mouse.down();page.mouse.move(r['x']+40,r['y']+20);page.wait_for_timeout(520);page.mouse.up();assert overlay.is_hidden()
   # The sheet fits narrow screens and both themes; cancellation never rounds the value.
   for light in [True,False]:
    page.evaluate('(v)=>applyLightMode(v)',light);r=weight.bounding_box();page.mouse.move(r['x']+20,r['y']+20);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
    sheet=page.locator('.record-wheel-sheet').bounding_box();assert sheet['x']>=0 and sheet['x']+sheet['width']<=width+.1
    assert abs(sheet['width']-r['width'])<.1 and abs(sheet['x']-r['x'])<.1,(sheet,r)
    assert abs(sheet['height']-r['height']*3)<.1 and abs(sheet['y']+sheet['height']/2-r['y']-r['height']/2)<.1,(sheet,r)
    assert overlay.evaluate("el=>getComputedStyle(el).backgroundColor")=='rgba(0, 0, 0, 0)'
    assert weight.evaluate("el=>getComputedStyle(el).visibility")=='hidden'

    wr=wheel.bounding_box();wx=wr['x']+wr['width']/2;wy=wr['y']+wr['height']*.75
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':wx,'y':wy}]})
    for offset in [8,16,28,40,55]:
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':wx,'y':wy-offset}]});page.wait_for_timeout(30)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(900)
    assert wheel.evaluate('el=>el.scrollTop')>44
    wheel.focus();page.keyboard.press('End');assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='500'
    page.keyboard.press('Home');assert page.locator('.record-wheel-option[aria-selected="true"]').inner_text()=='0'
    wheel.evaluate('el=>el.scrollTop=5*44');page.wait_for_timeout(80)
    page.screenshot(path='/tmp/record-wheel-'+str(width)+'-'+str(light)+'.png')
    page.locator('[data-wheel-cancel]').click();assert weight.input_value()=='2.5'
    assert weight.evaluate("el=>getComputedStyle(el).visibility")=='visible'
   # A collapsed input still anchors the wheel to its actual displayed dimensions.
   page.evaluate("document.getElementById('recordFloatBarTab2').style.transform='scale(.8)'");page.wait_for_timeout(300)
   r=weight.bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
   sheet=page.locator('.record-wheel-sheet').bounding_box()
   assert abs(sheet['width']-r['width'])<.1 and abs(sheet['height']-3*r['height'])<.2,(sheet,r)
   page.locator('[data-wheel-cancel]').click();assert weight.input_value()=='2.5'
   page.evaluate("document.getElementById('recordFloatBarTab2').style.transform='scale(1)'");page.wait_for_timeout(300)
   # Existing save remains the only operation that creates a workout set.
   weight.fill('55');page.locator('#recordAdd').click();page.wait_for_timeout(400)
   assert page.evaluate('records.bench.length')==before+1
   # Accessory inputs share the same gesture path and do not create records on confirm.
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(300)
   page.evaluate("openExerciseDetail('휠 테스트');document.getElementById('acc-weight').value='25'")
   acc=page.locator('#acc-weight');r=acc.bounding_box();page.mouse.move(r['x']+20,r['y']+20);page.mouse.down();page.wait_for_timeout(520);page.mouse.up()
   assert overlay.is_visible();wheel.evaluate('el=>el.scrollTop=8*44');page.wait_for_timeout(80)
   page.locator('[data-wheel-confirm]').click();assert acc.input_value()=='40'
   assert page.evaluate("accRecordsByExercise['휠 테스트'].length")==0
   print('PASS: short touch, real-touch hold without focus, 5kg and 1rep wheels, confirm/cancel, keyboard, movement cancellation and unchanged explicit save')
   c.close()
  b.close()
finally:server.terminate();server.wait()
