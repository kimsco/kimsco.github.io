"""Announcement bottom-sheet navigation and remaining inbox content."""
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
   values=page.evaluate('''async()=>{openAnnouncementModal();let ys=[];for(let i=0;i<24;i++){await new Promise(requestAnimationFrame);ys.push(document.querySelector('#announcementModal .exercise-ref-modal-box').getBoundingClientRect().y)}return ys}''');assert max(values)-min(values)>20,values
   modal=page.locator('#announcementModal');sheet=modal.locator('.exercise-ref-modal-box');assert sheet.bounding_box()['y']<70;assert sheet.evaluate('e=>getComputedStyle(e).borderTopLeftRadius')=='44px'
   assert page.locator('.announcement-row').count()==2;assert page.locator('.announcement-row-title').all_text_contents()==['기록 입력, 탭 한 번으로 불러오기','휴식 스톱워치 추가!'];assert page.evaluate('ANNOUNCEMENTS.every(a=>announcementReadIds.includes(a.id))')
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light);assert modal.evaluate('e=>e.scrollWidth<=innerWidth')
    bounds=sheet.bounding_box();title=page.locator('#announcementModalTitle');pill=title.bounding_box();close=page.locator('#announcementModalCloseBtn').bounding_box()
    assert abs((pill['x']-bounds['x'])-(pill['y']-bounds['y']))<1
    assert abs((pill['x']-bounds['x'])-(bounds['x']+bounds['width']-close['x']-close['width']))<1
    assert abs(pill['y']-close['y'])<1 and pill['height']==close['height']==44
    assert title.evaluate('e=>getComputedStyle(e).fontSize')=='19px'
    assert 'blur(14px)' in title.evaluate('e=>getComputedStyle(e).backdropFilter')
    page.screenshot(path=f'/tmp/announcement-sheet-{width}-{light}.png')
   cdp=context.new_cdp_session(page)
   def pull(dy):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':width/2,'y':220}]})
    for i in range(1,11):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':width/2,'y':220+dy*i/10}]});page.wait_for_timeout(16)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(400)
   pull(60);assert modal.is_visible();pull(200);assert modal.is_hidden();assert not page.locator('html').evaluate('e=>e.classList.contains("announcement-modal-open")')
   page.locator('#openAnnouncementBtn').click();page.wait_for_timeout(400);page.locator('#announcementModalCloseBtn').click();page.wait_for_timeout(110);blur=modal.evaluate('e=>parseFloat(getComputedStyle(e).backdropFilter.match(/[0-9.]+/)[0])');assert 0<blur<6,blur;page.wait_for_timeout(290);assert modal.is_hidden()
   page.locator('#openAnnouncementBtn').click();page.wait_for_timeout(400);page.mouse.click(width/2,10);page.wait_for_timeout(400);assert modal.is_hidden()
   page.evaluate('openAnnouncementModal();closeAnnouncementModal();openAnnouncementModal()');page.wait_for_timeout(450);assert modal.is_visible();page.keyboard.press('Escape');page.wait_for_timeout(400);assert modal.is_hidden();assert not errors,errors
   print('PASS sheet entrance, remaining content, read state, themes, pull/X/backdrop/Escape and reopen',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
