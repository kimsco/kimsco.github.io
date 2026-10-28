"""Return-to-top motion on real record save paths; isolated Firebase only."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8210','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   fixture=(root/'tests/firebase-fixture.js').read_text()
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8210/');page.wait_for_timeout(800)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(400)
   page.evaluate("""()=>{
    window.scrollFixture=[];
    for(let day=0;day<24;day++)for(let i=0;i<5;i++){
     const d=new Date();d.setDate(d.getDate()-day);
     const date=String(d.getFullYear()).slice(-2)+'.'+String(d.getMonth()+1).padStart(2,'0')+'.'+String(d.getDate()).padStart(2,'0');
     scrollFixture.push({date,weight:50+i,reps:5,sets:1,localId:'fixture-'+day+'-'+i,createdAt:d.getTime()-i});
    }
    records.bench=scrollFixture.map(x=>({...x}));renderActiveBox();
   }""")
   arrow=page.locator('#recordScrollTop');assert arrow.get_attribute('aria-hidden')=='true'
   page.evaluate('benchBox.scrollTop=650');page.wait_for_timeout(700)
   assert arrow.get_attribute('aria-hidden')=='false',page.evaluate("Array.from(document.querySelectorAll('[id$=Overlay],[id$=Modal]')).filter(e=>!e.classList.contains('hidden')&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).pointerEvents!=='none').map(e=>e.id)")
   rect=arrow.bounding_box();assert 0<=rect['x'] and rect['x']+32<=width and rect['width']==32 and abs(rect['x']+16-width/2)<1
   assert page.evaluate("document.elementFromPoint(parseFloat(recordScrollTop.style.left),parseFloat(recordScrollTop.style.top)+16)===recordScrollTop || recordScrollTop.contains(document.elementFromPoint(parseFloat(recordScrollTop.style.left),parseFloat(recordScrollTop.style.top)+16))")
   # Real shortcut click starts a multi-frame movement and reaches zero promptly.
   arrow.click();page.wait_for_timeout(70);mid=page.evaluate('benchBox.scrollTop');assert 0<mid<650,mid
   page.wait_for_timeout(400);assert page.evaluate('benchBox.scrollTop')==0 and arrow.get_attribute('aria-hidden')=='true'
   # Invalid input doesn't move. First collapsed-pill click still only expands.
   page.evaluate("benchBox.scrollTop=650;recordWeight.value='';recordReps.value='';");page.wait_for_timeout(700)
   before=page.evaluate('records.bench.length');page.locator('#recordAdd').tap();page.wait_for_timeout(600)
   assert page.evaluate('records.bench.length')==before and page.evaluate('benchBox.scrollTop')>600
   page.locator('#recordAdd').tap();page.wait_for_timeout(100);assert page.evaluate('benchBox.scrollTop')>600
   page.evaluate("recordWeight.value='60';recordReps.value='8';")
   frames=page.evaluate("""async()=>{const out=[];recordAdd.click();for(let i=0;i<32;i++){await new Promise(requestAnimationFrame);out.push(benchBox.scrollTop);}return out;}""")
   assert page.evaluate('records.bench.length')==before+1
   assert any(0<x<600 for x in frames) and frames[-1]==0,frames
   # Keyboard/reduced-motion users can use the button; another tab hides it.
   page.evaluate('benchBox.scrollTop=650');page.wait_for_timeout(700)
   page.evaluate('openNavDrawer()');page.wait_for_timeout(50);assert arrow.get_attribute('aria-hidden')=='true'
   page.evaluate('closeNavDrawer()');page.wait_for_timeout(350);assert arrow.get_attribute('aria-hidden')=='false'
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(200);assert arrow.get_attribute('aria-hidden')=='true'
   page.evaluate('document.getElementById("closeSettingsBtn").click()');page.wait_for_timeout(350)
   page.emulate_media(reduced_motion='reduce');arrow.focus();page.keyboard.press('Enter');page.wait_for_timeout(50);assert page.evaluate('benchBox.scrollTop')==0
   page.emulate_media(reduced_motion='no-preference')
   # The accessory history has its own scroll container and the same save behavior.
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(300)
   page.evaluate("""()=>{currentExercises=['스크롤 테스트'];accRecordsByExercise['스크롤 테스트']=scrollFixture.map((x,i)=>({...x,id:'acc-'+i,exercise:'스크롤 테스트',part:'chest'}));renderExercises();openExerciseDetail('스크롤 테스트');document.getElementById('acc-records').scrollTop=650;}""")
   page.wait_for_timeout(700);assert arrow.get_attribute('aria-hidden')=='false'
   for light in [True,False]:
    page.evaluate('(v)=>applyLightMode(v)',light);page.wait_for_timeout(50)
    assert arrow.evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgba(30, 30, 30, 0.96)'
    assert abs(arrow.bounding_box()['x']+16-width/2)<1
    page.screenshot(path=f'/tmp/record-scroll-{width}-{light}.png')
   page.locator('#recordFloatBarAcc button').tap();page.wait_for_timeout(600)
   page.evaluate("document.getElementById('acc-weight').value='30';document.getElementById('acc-reps').value='9';")
   frames=page.evaluate("""async()=>{const out=[];await addAccessorySet();for(let i=0;i<32;i++){await new Promise(requestAnimationFrame);out.push(document.getElementById('acc-records').scrollTop);}return out;}""")
   assert any(0<x<600 for x in frames) and frames[-1]==0,frames
   assert page.evaluate("accRecordsByExercise['스크롤 테스트'].length")==121
   # Interrupted motion stops without pulling the user back up afterwards.
   page.evaluate("document.getElementById('acc-records').scrollTop=650");page.wait_for_timeout(700);arrow.click();page.wait_for_timeout(60)
   page.evaluate("document.getElementById('acc-records').dispatchEvent(new WheelEvent('wheel',{bubbles:true,deltaY:100}));document.getElementById('acc-records').scrollTop=500")
   page.wait_for_timeout(450);assert page.evaluate("document.getElementById('acc-records').scrollTop")==500
   # A captured save cannot scroll a different exercise/tab after navigation.
   page.evaluate("window.savedScrollContext=MFRecordScroll.capture(document.getElementById('acc-records'));closeExerciseDetail();MFRecordScroll.afterSave(savedScrollContext)")
   page.evaluate("""()=>{currentExercises=Array.from({length:30},(_,i)=>'목록 테스트 '+i);renderExercises();exerciseScreen.scrollTop=500;}""")
   page.wait_for_timeout(700);assert arrow.get_attribute('aria-hidden')=='false'
   arrow.click();page.wait_for_timeout(450);assert page.evaluate('exerciseScreen.scrollTop')==0
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(300)
   page.evaluate('benchBox.scrollTop=650');page.wait_for_timeout(700)
   # Simulate a rejected local outbox write, without accessing any real account.
   page.on('dialog',lambda dialog:dialog.dismiss())
   page.evaluate("""()=>{window.originalPrivateWrite=privateWrite;window.originalScrollUser=fixture.auth.currentUser;fixture.auth.currentUser={uid:'fixture-failed-write'};privateWrite=async()=>{throw Error('isolated write failure');};recordWeight.value='60';recordReps.value='8';}""")
   before=page.evaluate('records.bench.length')
   page.locator('#recordAdd').tap();page.wait_for_timeout(600);page.locator('#recordAdd').tap();page.wait_for_timeout(100)
   assert page.evaluate('benchBox.scrollTop')>600 and page.evaluate('records.bench.length')==before
   page.evaluate('privateWrite=originalPrivateWrite;fixture.auth.currentUser=originalScrollUser;')
   page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(100);assert arrow.get_attribute('aria-hidden')=='true'
   assert not errors,errors
   print('PASS save animation, manual shortcut, first-pill wake, validation, cancellation, overlays, themes and reduced motion:',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
