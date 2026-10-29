"""Home actions retain their geometry throughout full-to-mini stopwatch transitions."""
from pathlib import Path
import subprocess,time,sys
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8222','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in ([390] if '--report-only' in sys.argv else [320,390]):
   context=browser.new_context(viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   context.add_init_script("localStorage.setItem('mf_rest_timer_enabled','1')")
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8222');page.wait_for_timeout(1500)
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(350)
   page.locator('#recordWeight').fill('60');page.locator('#recordReps').fill('5');page.locator('#recordAdd').click();page.wait_for_timeout(1100)
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    for paused in [False,True]:
     page.evaluate('p=>{if(!!restTimerPausedAt!==p)toggleRestTimerPause()}',paused)
     for source in ['tab2','tab4']:
      page.locator('.bottomTab .tabBtn[data-target="'+source+'"]').click();page.wait_for_timeout(380)
      trace=page.evaluate('''async()=>{
       document.querySelector('.bottomTab .tabBtn[data-target="tab1"]').click();
       const frames=[];
       do {
        frames.push(['openAnnouncementBtn','openSettingsBtn'].map(id=>{
         const r=document.getElementById(id).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};
        }));
        await new Promise(requestAnimationFrame);
       } while(restTimerMotion.snapshot());
       frames.push(['openAnnouncementBtn','openSettingsBtn'].map(id=>{
        const r=document.getElementById(id).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};
       }));
       return frames;
      }''')
      deltas=[max(abs(frame[i][key]-trace[-1][i][key]) for frame in trace for key in ['x','y','width','height']) for i in [0,1]]
      if '--report-only' in sys.argv:
       print('BEFORE action position drift (px)',deltas);browser.close();raise SystemExit(0)
      assert max(deltas)<.2,(width,light,paused,source,deltas)
      assert len(trace)>5 and page.locator('#restTimerMiniDisplay').is_visible()
   assert not errors,errors
   print('PASS stable home actions during timer shrink from 3대/기록, running/paused, dark/light',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
