"""Lift graph sheet appearance, chart modes, gestures and reopen safety."""
import subprocess,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
chart=urllib.request.urlopen('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',timeout=25).read()
server=subprocess.Popen(['python','-m','http.server','8215','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   def route(r):
    url=r.request.url
    r.fulfill(body=fixture if '/firebase-app-compat.js' in url else chart if 'chart.js' in url else '',content_type='application/javascript')
   context.route('https://**/*',route);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8215');page.wait_for_timeout(1400)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(300)
   page.evaluate("records.bench=[{date:'26.10.28',weight:60,reps:5}]")
   page.locator('.folderBtn[data-target="benchBox"]').click();page.wait_for_timeout(450)
   sheet=page.locator('#graphSheet');assert sheet.is_visible();assert page.locator('#sheetTitle').inner_text()=='BENCH'
   assert page.evaluate('!!chartInstance')
   box=sheet.bounding_box();assert abs(box['height']-844*.78)<1 and abs(box['y']+box['height']-844)<1,box
   assert sheet.evaluate('e=>getComputedStyle(e).borderTopLeftRadius')=='44px'
   assert page.locator('#sheetClose').bounding_box()['width']==44
   assert abs(page.locator('#sheetClose').bounding_box()['y']-page.locator('#sheetTitle').bounding_box()['y'])<1
   assert 'blur(14px)' in page.locator('#sheetTitle').evaluate('e=>getComputedStyle(e).backdropFilter')
   assert 'blur(6px)' in page.locator('#graphOverlay').evaluate('e=>getComputedStyle(e).backdropFilter')
   assert page.locator('#sheetHandle').count()==0
   page.locator('.segBtn[data-mode="weight"]').click();assert page.evaluate('graphMode')=='weight';assert page.evaluate('chartInstance.data.datasets[0].data[0]')==60
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light);assert sheet.evaluate('e=>e.scrollWidth<=innerWidth')
    page.screenshot(path=f'/tmp/graph-sheet-{width}-{light}.png')
   blur=page.evaluate("""()=>new Promise(resolve=>{document.getElementById('sheetClose').click();setTimeout(()=>resolve(parseFloat(getComputedStyle(graphOverlay).backdropFilter.slice(5))),80)})""");assert 0<blur<6,blur
   page.wait_for_timeout(280);assert sheet.is_hidden()
   page.evaluate("openSheet('squat');closeSheet();openSheet('dead')");page.wait_for_timeout(450);assert sheet.is_visible();assert page.locator('#sheetTitle').inner_text()=='DEADLIFT'
   cdp=context.new_cdp_session(page)
   def pull(distance):
    start_y=sheet.bounding_box()['y']+75
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':width/2,'y':start_y}]})
    for i in range(1,11):
     cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':width/2,'y':start_y+distance*i/10}]});page.wait_for_timeout(16)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(400)
   pull(60);assert sheet.is_visible();pull(200);assert sheet.is_hidden()
   page.evaluate("openSheet('bench')");page.wait_for_timeout(400);page.keyboard.press('Escape');page.wait_for_timeout(380);assert sheet.is_hidden()
   assert not errors,errors
   print('PASS lift chart, styles, themes, modes, blur fade, pulls, rapid reopen and Escape',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
