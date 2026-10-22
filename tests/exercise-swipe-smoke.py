"""Exercise link swipe resistance, velocity and cancellation; fake Firebase."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8198','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width,height in [(360,880)]:
   c=b.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
   fixture=(root/'tests/firebase-fixture.js').read_text()
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();page.goto('http://127.0.0.1:8198/');page.wait_for_timeout(700)
   page.evaluate("""()=>{window.details=0;window.links=0;const host=document.createElement('div');host.style.cssText='position:fixed;top:140px;left:20px;width:280px;z-index:200000;background:black';document.body.append(host);window.swipeCards=[];for(let i=0;i<2;i++){const wrap=document.createElement('div');wrap.className='exercise-row-wrap';const ref=document.createElement('div');ref.className='exercise-ref-action';ref.textContent='링크';const card=document.createElement('div');card.className='exercise-card';card.textContent='종목 '+i;card.addEventListener('click',()=>{if(card.classList.contains('swiped'))closeExerciseSwipe(card);else details++;});ref.addEventListener('click',()=>{links++;closeExerciseSwipe(card);});wrap.append(ref,card);host.append(wrap);setupExerciseSwipe(card);swipeCards.push(card);}}""")
   def event(kind,x,y=170,index=0):
    page.evaluate("""a=>{const card=swipeCards[a.index],touch=new Touch({identifier:1,target:card,clientX:a.x,clientY:a.y});card.dispatchEvent(new TouchEvent(a.kind,{touches:a.kind==='touchend'||a.kind==='touchcancel'?[]:[touch],changedTouches:[touch],bubbles:true,cancelable:true}));}""",dict(kind=kind,x=x,y=y,index=index))
   def x(index=0):return page.evaluate('(i)=>new DOMMatrixReadOnly(getComputedStyle(swipeCards[i]).transform).m41',index)
   def opened(index=0):return page.evaluate('(i)=>swipeCards[i].classList.contains("swiped")',index)
   # Beyond the normal 58px reveal there is capped resistance, not a hard stop.
   event('touchstart',240);event('touchmove',60)
   assert -76<x()<-58,x()
   event('touchend',60);page.wait_for_timeout(450);assert abs(x()+58)<.01 and opened()
   # A short fast closing flick respects velocity and does not open a detail on release.
   event('touchstart',150);page.wait_for_timeout(25);event('touchmove',170);event('touchend',170)
   page.evaluate('swipeCards[0].click()');assert page.evaluate('details')==0
   page.wait_for_timeout(450);assert abs(x())<.01 and not opened()
   # Slow short swipe closes; fast short swipe opens with less than half the distance.
   event('touchstart',240);event('touchmove',220);page.wait_for_timeout(150);event('touchend',220)
   page.wait_for_timeout(450);assert not opened()
   event('touchstart',240);page.wait_for_timeout(25);event('touchmove',220);event('touchend',220)
   page.wait_for_timeout(450);assert opened() and abs(x()+58)<.01
   # Starting the second row closes the first; cancellation restores its old state.
   event('touchstart',240,index=1);event('touchmove',180,index=1);event('touchcancel',180,index=1)
   page.wait_for_timeout(450);assert not opened(0) and not opened(1)
   assert not page.evaluate('swipeCards[1].parentElement.querySelector(".exercise-ref-action").classList.contains("revealed")')
   # Vertical gesture passes through and leaves the row closed.
   event('touchstart',240);event('touchmove',242,110);event('touchend',242,110)
   page.wait_for_timeout(450);assert not opened()
   # Link action remains clickable after settling.
   event('touchstart',240);event('touchmove',170);event('touchend',170);page.wait_for_timeout(450)
   page.evaluate('swipeCards[0].parentElement.querySelector(".exercise-ref-action").click()')
   assert page.evaluate('links')==1;page.wait_for_timeout(450);assert not opened()
   page.emulate_media(reduced_motion='reduce');event('touchstart',240);event('touchmove',170);event('touchend',170)
   assert abs(x()+58)<.01
   page.emulate_media(reduced_motion='no-preference');page.evaluate('closeExerciseSwipe(swipeCards[0])');page.wait_for_timeout(450)
   r=page.evaluate('swipeCards[0].getBoundingClientRect().toJSON()');tx=r['x']+r['width']*.7;ty=r['y']+r['height']/2
   cdp=c.new_cdp_session(page)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':tx,'y':ty}]})
   for offset in [12,24,40,60,80]:
    cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':tx-offset,'y':ty}]});page.wait_for_timeout(25)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(450)
   assert opened() and page.evaluate('details')==0
   page.touchscreen.tap(r['right']-25,ty);page.wait_for_timeout(450)
   assert page.evaluate('links')==2 and not opened()
   print('PASS: resisted overdrag, endpoint settling, short flick open/close, click suppression, one open row, cancellation, vertical gesture, link action and reduced motion')
   c.close()
  b.close()
finally:server.terminate();server.wait()
