"""Repeated outside taps never restart explicit wheel dismissal; idle re-grab remains."""
from pathlib import Path
import subprocess,time,sys
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8226','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in ([390] if '--report-only' in sys.argv else [320,390]):
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8226');page.wait_for_timeout(1500)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(350)
   overlay=page.locator('.record-wheel-overlay');sheet=page.locator('.record-wheel-sheet');wheel=page.locator('.record-wheel-list')
   def open_wheel(input_id):
    r=page.locator('#'+input_id).bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x,y-6);page.mouse.up();page.wait_for_timeout(210)
    assert overlay.is_visible()
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    for input_id,method in [('recordWeight','mouse'),('recordReps','touch')]:
     page.evaluate("recordWeight.value='50';recordReps.value='7';window.commitCount=0;window.commitListener=()=>commitCount++")
     page.locator('#'+input_id).evaluate("e=>e.addEventListener('change',commitListener)")
     before=page.evaluate('records.bench.length');open_wheel(input_id)
     page.evaluate('''()=>{
      window.commitCount=0;window.fadeTrace=[];window.fadeStart=performance.now();window.fadeEnd=null;
      const overlay=document.querySelector('.record-wheel-overlay'),sheet=overlay.querySelector('.record-wheel-sheet');
      function sample(){
       fadeTrace.push({at:performance.now(),opacity:Number(getComputedStyle(sheet,'::before').opacity)});
       if(overlay.hidden){fadeEnd=performance.now();return;}requestAnimationFrame(sample);
      }requestAnimationFrame(sample);
     }''')
     tap=page.mouse.click if method=='mouse' else page.touchscreen.tap
     tap(5,200);page.wait_for_timeout(90);tap(5,200);page.wait_for_timeout(70);tap(5,200);page.wait_for_timeout(360)
     trace=page.evaluate('({frames:fadeTrace,duration:fadeEnd-fadeStart,commits:commitCount})')
     jumps=[trace['frames'][i]['opacity']-trace['frames'][i-1]['opacity'] for i in range(1,len(trace['frames'])-1)]
     if '--report-only' in sys.argv:
      print('BEFORE opacity rebound',max(jumps),'duration',trace['duration']);browser.close();raise SystemExit(0)
     assert max(jumps,default=0)<.025,trace
     assert 230<trace['duration']<420,trace
     assert overlay.is_hidden() and trace['commits']==1,trace
     assert page.evaluate('records.bench.length')==before
     assert not page.locator('#'+input_id).evaluate("e=>e.classList.contains('record-wheel-source')")
     page.locator('#'+input_id).evaluate("e=>e.removeEventListener('change',commitListener)")
   # An outside press during automatic fade also continues fading without a rebound.
   open_wheel('recordWeight');page.wait_for_timeout(580)
   before_opacity=float(sheet.evaluate("e=>getComputedStyle(e,'::before').opacity"))
   page.mouse.move(5,200);page.mouse.down();page.wait_for_timeout(70)
   assert float(sheet.evaluate("e=>getComputedStyle(e,'::before').opacity"))<=before_opacity+.01
   page.mouse.up();page.wait_for_timeout(300);assert overlay.is_hidden()
   # Automatic idle fade can still be interrupted by deliberately holding the wheel.
   open_wheel('recordWeight');page.wait_for_timeout(580)
   opacity=float(sheet.evaluate("e=>getComputedStyle(e,'::before').opacity"));assert 0<opacity<.5,opacity
   r=wheel.bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down();page.wait_for_timeout(650)
   assert overlay.is_visible() and sheet.evaluate("e=>getComputedStyle(e,'::before').opacity")=='0.5'
   page.mouse.up();page.keyboard.press('Escape');assert overlay.is_hidden()
   # Dismissal state is cleared for the next open and explicit keyboard commit.
   open_wheel('recordWeight');page.keyboard.press('Enter');assert overlay.is_hidden()
   assert not errors,errors
   print('PASS monotonic outside fade, touch/mouse repeated taps, one commit, idle re-grab and reopen',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
