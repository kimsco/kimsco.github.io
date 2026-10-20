"""Home mode frame coupling, persistence and action regression checks; isolated Firebase."""
import subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
p=subprocess.Popen([sys.executable,'-m','http.server','8197','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  fixture=(root/'tests/firebase-fixture.js').read_text();c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8197/');page.wait_for_timeout(650)
  assert page.locator('#homeGreeting').count()==0
  assert page.locator('#homeModeSwitch').is_visible()
  viewport=page.locator('#homeModeViewport').bounding_box()
  assert abs(viewport['x'])<.1 and abs(viewport['width']-390)<.1,viewport
  assert abs(page.locator('.home-title-row').bounding_box()['x']-27)<.1
  top=page.locator('#homeModeSwitch').bounding_box()
  assert top['y']<75,top
  for opening in [True,False]:
   samples=page.evaluate('''async opening=>{const out=[];const base=document.getElementById('homeModeSwitch').getBoundingClientRect().left-Number(new DOMMatrix(getComputedStyle(document.querySelector('.app')).transform).m41);opening?openNavDrawer():closeNavDrawer();for(let i=0;i<22;i++){await new Promise(requestAnimationFrame);out.push([document.getElementById('homeModeSwitch').getBoundingClientRect().left-base,new DOMMatrix(getComputedStyle(document.querySelector('.app')).transform).m41]);}return out;}''',opening)
   assert all(abs(pill-app)<.2 for pill,app in samples),samples
  page.evaluate("setAppPushTransition('none');setAppPush(25)")
  assert abs(page.locator('#homeModeSwitch').bounding_box()['x']-top['x']-25)<.2
  page.evaluate("setAppPush(0)")
  assert float(page.locator('#homeModeSwitch').evaluate('(el)=>getComputedStyle(el).opacity'))==1
  page.wait_for_timeout(5200)
  assert abs(float(page.locator('#homeModeSwitch').evaluate('(el)=>getComputedStyle(el).opacity'))-.5)<.01
  page.evaluate("document.querySelector('.app').scrollTop=180")
  page.wait_for_timeout(260)
  scrolled=page.locator('#homeModeSwitch').bounding_box()
  assert abs(top['y']-scrolled['y'])<.1 and abs(top['x']-scrolled['x'])<.1
  assert abs(float(page.locator('#homeModeSwitch').evaluate('(el)=>getComputedStyle(el).opacity'))-.5)<.01
  page.screenshot(path='/tmp/home-mode-floating-scroll.png')
  page.evaluate("document.querySelector('.app').scrollTop=0")
  page.wait_for_timeout(260)
  assert abs(float(page.locator('#homeModeSwitch').evaluate('(el)=>getComputedStyle(el).opacity'))-.5)<.01
  page.locator('.bottomTab .tabBtn[data-target="tab2"]').click()
  assert not page.locator('#homeModeSwitch').is_visible()
  page.locator('.bottomTab .tabBtn[data-target="tab1"]').click()
  assert page.locator('#homeModeSwitch').is_visible()

  trace='''async on=>{
   (on?homeModeFocus:homeModeBasic).click();const frames=[];
   while(homeModeFrame){
    const v=homeModeViewport.getBoundingClientRect(),n=homeNormalContent.getBoundingClientRect(),f=homeSeriousModeScreen.getBoundingClientRect(),t=document.querySelector('.home-mode-thumb'),r=t.getBoundingClientRect(),s=homeModeSwitch.getBoundingClientRect();
    frames.push({p:homeModeProgress,width:v.width,n:n.left-v.left,f:f.left-v.left,thumb:r.left-s.left-4,thumbWidth:r.width});
    await new Promise(requestAnimationFrame);
   }return frames;
  }'''
  for light in [False,True]:
   page.evaluate('(v)=>applyLightMode(v)',light)
   for on in [True,False]:
    frames=page.evaluate(trace,on);assert len(frames)>5
    assert any(0<f['p']<1 for f in frames)
    for f in frames:
     assert abs(f['n']+f['width']*f['p'])<.2,f
     assert abs(f['f']-f['width']*(1-f['p']))<.2,f
     assert abs(f['thumb']-f['thumbWidth']*f['p'])<.2,f
    assert page.evaluate('homeModeProgress')==(1 if on else 0)
    assert page.locator('#seriousModeToggle').evaluate("el=>el.classList.contains('active')")==on
    page.screenshot(path='/tmp/home-'+('focus' if on else 'basic')+'-'+('light' if light else 'dark')+'.png')
   page.evaluate('applySeriousMode(true)');page.wait_for_timeout(100)
   before=page.evaluate('homeModeProgress');page.evaluate('applySeriousMode(false)');assert abs(page.evaluate('homeModeProgress')-before)<.15
   page.wait_for_timeout(450);assert page.evaluate('homeModeProgress')==0
  page.evaluate('applySeriousMode(true)');page.wait_for_timeout(450);page.reload();page.wait_for_timeout(700)
  assert page.evaluate('homeModeProgress')==1 and page.locator('#homeModeFocus').get_attribute('aria-selected')=='true'
  assert page.locator('#homeNormalContent').evaluate('(el)=>el.inert')
  page.evaluate('applySeriousMode(false,{animate:false})');page.reload();page.wait_for_timeout(700)
  assert page.evaluate('homeModeProgress')==0 and page.locator('#homeModeBasic').get_attribute('aria-selected')=='true'
  assert page.locator('#homeSeriousModeScreen').evaluate('(el)=>el.inert')
  page.emulate_media(reduced_motion='reduce')
  page.locator('#homeModeFocus').focus();page.keyboard.press('ArrowLeft')
  assert page.evaluate('homeModeProgress')==0 and page.evaluate('homeModeFrame')==0
  page.keyboard.press('ArrowRight');assert page.evaluate('homeModeProgress')==1
  page.evaluate('applySeriousMode(false,{animate:false})')
  page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(300)
  assert page.locator('.home-diet-card').count()==1
  page.locator('#homeDietQuickBtn').scroll_into_view_if_needed();page.locator('#homeDietQuickBtn').click();assert page.locator('#quickAddMealModal').is_visible()
  assert not errors,errors
  print('PASS: pill and adjoining pages share frame progress in both themes; rapid reversal, reload persistence, settings synchronization, inert panel and diet action preserved')
  b.close()
finally:p.terminate();p.wait()
