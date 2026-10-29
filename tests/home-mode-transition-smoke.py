"""Compositor transitions, reversals, layout churn, persistence and accessibility."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8221','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8221');page.wait_for_timeout(1500)
   quote_order=page.locator('.home-focus-quote-plain').all_text_contents()
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    for on in [True,False]:
     result=page.evaluate('''async on=>{
      let heightWrites=0;const frames=[];
      const observer=new MutationObserver(()=>heightWrites++);observer.observe(homeModeViewport,{attributes:true,attributeFilter:['style']});
      applyHomeMode(on);
      while(homeModeMotion){
       const viewport=homeModeViewport.getBoundingClientRect(),normal=homeNormalContent.getBoundingClientRect(),focus=homeSeriousModeScreen.getBoundingClientRect(),thumb=homeModeThumb.getBoundingClientRect();
       frames.push({p:currentHomeModeProgress(),content:(viewport.left-normal.left)/viewport.width,focus:(focus.left-viewport.left)/viewport.width,thumb:new DOMMatrix(getComputedStyle(homeModeThumb).transform).m41/thumb.width});
       await new Promise(requestAnimationFrame);
      }
      observer.disconnect();return {frames,heightWrites};
     }''',on)
     frames=result['frames'];assert len(frames)>5,frames;assert result['heightWrites']<=3,result
     assert any(.1<f['p']<.9 for f in frames)
     for f in frames:
      assert abs(f['content']-f['thumb'])<.005,f
      assert abs(f['focus']-(1-f['content']))<.005,f
     assert page.evaluate('homeModeProgress')==int(on)
     assert page.locator('#homeModeFocus').get_attribute('aria-selected')==str(on).lower()
   # Reverse mid-flight without returning to the previous endpoint.
   delta=page.evaluate('''async()=>{
    applyHomeMode(true);await new Promise(r=>setTimeout(r,90));
    const before=new DOMMatrix(getComputedStyle(homeModeTrack).transform).m41;
    applyHomeMode(false);const after=new DOMMatrix(getComputedStyle(homeModeTrack).transform).m41;
    return Math.abs(after-before);
   }''');assert delta<1,delta
   page.wait_for_timeout(450);assert page.evaluate('homeModeProgress')==0
   page.evaluate('applyHomeMode(true)');page.wait_for_timeout(50);page.evaluate('applyHomeMode(false)');page.wait_for_timeout(50);page.evaluate('applyHomeMode(true)');page.wait_for_timeout(450)
   assert page.evaluate('homeModeProgress')==1 and not page.evaluate('!!homeModeMotion')
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(200);page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(250)
   assert page.locator('.home-focus-quote-plain').all_text_contents()==quote_order
   page.reload();page.wait_for_timeout(1500);assert page.evaluate('homeModeProgress')==1
   assert page.locator('#homeNormalContent').evaluate('e=>e.inert')
   page.emulate_media(reduced_motion='reduce');page.evaluate('applyHomeMode(false)');assert not page.evaluate('!!homeModeMotion') and page.evaluate('homeModeProgress')==0
   page.locator('#homeModeBasic').focus();page.keyboard.press('ArrowRight');assert page.evaluate('homeModeProgress')==1
   assert not errors,errors
   print('PASS smooth coupled frames, bounded height writes, reversals, tabs, persistence and reduced motion',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
