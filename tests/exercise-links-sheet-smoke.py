"""Reference markers and editable link-sheet behavior with isolated data."""
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
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(400)
   page.evaluate('''()=>{document.getElementById('exercise-screen').style.display='block';currentPart='chest';currentExercises=['링크 종목','빈 종목'];exerciseRefLinks={};addExerciseRefLink('링크 종목','https://example.test/guide');renderExercises({onOpenDetail:name=>window.openedExercise=name});}''')
   cards=page.locator('#exercise-list .exercise-card');assert cards.count()==2;assert cards.nth(0).locator('.exercise-link-indicator').count()==1;assert cards.nth(1).locator('.exercise-link-indicator').count()==0
   cards.nth(0).click();assert page.evaluate('window.openedExercise')=='링크 종목'
   page.evaluate("openExerciseRefModal('링크 종목')");page.wait_for_timeout(450);modal=page.locator('#exerciseRefModal');sheet=modal.locator('.exercise-ref-modal-box');assert modal.is_visible();assert sheet.bounding_box()['y']<70
   # Add to the empty exercise and reflect the marker without rebuilding cards.
   page.locator('#exerciseRefModalCloseBtn').click();page.wait_for_timeout(400);page.evaluate("openExerciseRefModal('빈 종목')");page.wait_for_timeout(400);page.locator('#exerciseRefUrlInput').fill('https://example.test/second');page.locator('#exerciseRefAddBtn').click();assert cards.nth(1).locator('.exercise-link-indicator').count()==1
   page.locator('.exercise-ref-delete-btn').click();assert cards.nth(1).locator('.exercise-link-indicator').count()==0
   # Only the composer rises: the opaque sheet and header stay fixed to the bottom.
   before=sheet.bounding_box();header=modal.locator('.exercise-ref-modal-header').bounding_box()
   for keyboard_height in [240,300,420]:
    page.evaluate("height=>{Object.defineProperty(visualViewport,'height',{configurable:true,value:innerHeight-height});visualViewport.dispatchEvent(new Event('resize'))}",keyboard_height);page.wait_for_timeout(100)
    box=sheet.bounding_box();assert abs(box['y']-before['y'])<1 and abs(box['height']-before['height'])<1,box
    assert abs(box['y']+box['height']-844)<1,box
    assert abs(modal.locator('.exercise-ref-modal-header').bounding_box()['y']-header['y'])<1
    composer=modal.locator('.exercise-ref-composer').bounding_box();assert composer['y']+composer['height']<=844-keyboard_height,composer
    assert modal.evaluate('e=>getComputedStyle(e).bottom')=='0px'
   page.evaluate("delete visualViewport.height;visualViewport.dispatchEvent(new Event('resize'))");page.wait_for_timeout(100)
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light);assert modal.evaluate('e=>e.scrollWidth<=innerWidth')
    title=page.locator('#exerciseRefModalTitle');assert 'blur(14px)' in title.evaluate('e=>getComputedStyle(e).backdropFilter')
    composer=page.locator('.exercise-ref-composer');assert composer.evaluate('e=>getComputedStyle(e).borderRadius')=='999px'
    assert page.locator('#exerciseRefAddBtn').evaluate('e=>getComputedStyle(e).borderRadius')=='50%'
    assert page.locator('#exerciseRefUrlInput').evaluate('e=>getComputedStyle(e).fontSize')=='16px'
    page.screenshot(path=f'/tmp/exercise-links-sheet-{width}-{light}.png')
   cdp=context.new_cdp_session(page);cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':width/2,'y':140}]})
   for i in range(1,11):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':width/2,'y':140+200*i/10}]});page.wait_for_timeout(16)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(400);assert modal.is_hidden()
   page.evaluate("openExerciseRefModal('링크 종목')");page.wait_for_timeout(400);assert page.locator('.exercise-ref-row-link').get_attribute('href')=='https://example.test/guide';page.keyboard.press('Escape');page.wait_for_timeout(400);assert modal.is_hidden();assert not errors,errors
   print('PASS markers, card action, add/delete, sheet geometry, keyboard, themes and dismissal',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
