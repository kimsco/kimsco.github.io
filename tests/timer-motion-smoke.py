"""Frame geometry checks for coupled pill/time/icon motion; isolated Firebase only."""
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
chart=urllib.request.urlopen('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js').read()
fixture=(ROOT/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 def route(r):
  if '/firebase-app.js' in r.request.url:r.fulfill(body=fixture,content_type='application/javascript')
  elif 'firebasejs/' in r.request.url:r.fulfill(body='',content_type='application/javascript')
  elif 'chart.js' in r.request.url:r.fulfill(body=chart,content_type='application/javascript')
  else:r.abort()
 c.route('https://**/*',route)
 c.add_init_script("localStorage.setItem('mf_rest_timer_enabled','1')")
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(400)
 page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(400)
 page.locator('#recordWeight').fill('60');page.locator('#recordReps').fill('5');page.locator('#recordAdd').click();page.wait_for_timeout(1100)
 trace="""async target=>{
   const before=captureRestTimerMotionState(), frames=[];
   document.querySelector(`.bottomTab .tabBtn[data-target="${target}"]`).click();
   const first=restTimerMotion.snapshot();
   while(restTimerMotion.snapshot()){
     const s=restTimerMotion.snapshot();
     frames.push({state:s,time:MFRestMotion.textRect(document.querySelector('.mf-rest-motion-time')),icon:MFRestMotion.rect(document.querySelector('.mf-rest-motion-icon'))});
     await new Promise(requestAnimationFrame);
   }
   return {before,first,frames,after:captureRestTimerMotionState()};
 }"""
 def center(r):return (r['left']+r['width']/2,r['top']+r['height']/2)
 def check(t):
  assert len(t['frames'])>=5
  for key in ['pill','time','icon']:
   for prop in ['left','top','width','height']:
    assert abs(t['before'][key][prop]-t['first'][key][prop])<.1,(key,prop,t)
  start,end=t['before'],t['after']
  for f in t['frames']:
   state=f['state'];progress=(state['pill']['top']-start['pill']['top'])/(end['pill']['top']-start['pill']['top'])
   for key in ['time','icon']:
    actual=center(f[key]);a,z=center(start[key]),center(end[key])
    expected=[a[i]+(z[i]-a[i])*progress for i in range(2)]
    assert max(abs(actual[i]-expected[i]) for i in range(2))<1,(key,actual,expected)
  for key in ['time','icon']:
   assert abs(center(t['frames'][-1][key])[1]-center(end[key])[1])<2
 for light in [False,True]:
  page.evaluate('(v)=>applyLightMode(v)',light)
  for paused in [False,True]:
   page.evaluate('(p)=>{if(Boolean(restTimerPausedAt)!==p)toggleRestTimerPause()}',paused)
   down=page.evaluate(trace,'tab1');check(down)
   assert center(down['after']['icon'])[0]<center(down['before']['icon'])[0]
   assert center(down['after']['time'])[1]>center(down['before']['time'])[1]
   up=page.evaluate(trace,'tab2');check(up)
   assert center(up['after']['time'])[1]<center(up['before']['time'])[1]
 # Reverse before completion: the new animation starts at the exact displayed geometry.
 reversals=page.evaluate("""async()=>{
   const results=[];
   for(let i=0;i<12;i++){
     const before=captureRestTimerMotionState();
     document.querySelector(`.bottomTab .tabBtn[data-target="${i%2?'tab2':'tab1'}"]`).click();
     results.push({before,after:restTimerMotion.snapshot()});
     await new Promise(r=>setTimeout(r,30));
   }
   return results;
 }""")
 for pair in reversals:
  for key in ['pill','time','icon']:
   assert max(abs(pair['before'][key][prop]-pair['after'][key][prop]) for prop in ['left','top','width','height'])<.1
 page.wait_for_timeout(400)
 assert page.locator('.mf-rest-motion').count()==0
 assert page.locator('#restTimerDisplay').is_visible()
 # Manual stop during a transition removes the moving content and persisted state.
 page.locator('.bottomTab .tabBtn[data-target="tab1"]').click()
 page.evaluate('stopRestTimerManually()')
 assert page.locator('.mf-rest-motion').count()==0
 page.wait_for_timeout(1100)
 assert page.locator('.mf-rest-motion').count()==0
 assert not page.evaluate('restTimerActive')
 # A physical X press must not feed its animated button scale into pill geometry.
 for light in [False,True]:
  for paused in [False,True]:
   page.evaluate('(v)=>applyLightMode(v)',light)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click()
   page.locator('#recordWeight').fill('60');page.locator('#recordReps').fill('5')
   page.locator('#recordAdd').click();page.wait_for_timeout(1100)
   assert page.evaluate('restTimerActive')
   if paused:page.evaluate('toggleRestTimerPause()')
   before=page.locator('#restTimerCardBg').bounding_box()
   button=page.locator('#openNavDrawerBtn').bounding_box()
   page.mouse.move(button['x']+button['width']/2,button['y']+button['height']/2)
   page.mouse.down();page.wait_for_timeout(120)
   page.mouse.up()
   for delay in [0,50,100]:
    page.wait_for_timeout(delay)
    after=page.locator('#restTimerCardBg').bounding_box()
    assert after is not None
    assert max(abs(after[k]-before[k]) for k in ['x','y','width','height'])<.1,(before,after)
   page.wait_for_timeout(700)
   assert not page.evaluate('restTimerActive')
   assert page.locator('#restTimerCardBg').bounding_box() is None
 assert not errors,errors
 print('PASS: same-frame pill/time/icon geometry in both directions, running/paused, dark/light, 12 rapid reversals and manual stop without pill expansion')
 b.close()
