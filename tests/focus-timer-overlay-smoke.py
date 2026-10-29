"""Focus content paints behind floating mini timer, retaining normal home spacing."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8218','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844})
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   context.add_init_script("localStorage.setItem('mf_rest_timer_enabled','1')")
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8218');page.wait_for_timeout(1500)
   order=page.locator('.home-focus-quote-plain').all_text_contents()
   def check_normal():
    page.evaluate('applyHomeMode(false,{animate:false})');page.wait_for_timeout(100)
    actual=page.locator('.home-title-row').bounding_box()['y']
    expected=page.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topBarH'))+60")
    assert abs(actual-expected)<1,(actual,expected)
   def check_focus(label):
    page.evaluate('applyHomeMode(true,{animate:false})');page.wait_for_timeout(120)
    geo=page.evaluate('''()=>{
     const screen=homeSeriousModeScreen,header=document.querySelector('.topBar').getBoundingClientRect(),focus=screen.getBoundingClientRect();
     const quote=screen.querySelector('.home-focus-quote-page:not([hidden]) .home-focus-quote');
     screen.style.scrollSnapType='none';
     screen.scrollTop=0;
     screen.scrollTop=quote.getBoundingClientRect().top-(header.bottom+12);
     const rect=quote.getBoundingClientRect(),x=rect.left+3,y=header.bottom+20;
     return {top:focus.top,header:header.bottom,bottom:focus.bottom,nav:document.querySelector('.bottomTab').getBoundingClientRect().top,visible:document.elementsFromPoint(x,y).includes(quote),x,y};
    }''')
    assert abs(geo['top']-geo['header'])<1,geo
    assert abs(geo['bottom']-geo['nav'])<1,geo
    assert geo['visible'],geo
    page.screenshot(path=f'/tmp/focus-timer-{width}-{label}.png')
    page.evaluate("homeSeriousModeScreen.style.scrollSnapType='';homeSeriousModeScreen.scrollTop=0")
   check_normal();check_focus('off')
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(350)
   page.locator('#recordWeight').fill('60');page.locator('#recordReps').fill('5');page.locator('#recordAdd').click();page.wait_for_timeout(1200)
   page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(500)
   assert page.locator('#restTimerMiniDisplay').is_visible()
   check_normal()
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light);check_focus('running-'+str(light))
   page.evaluate('toggleRestTimerPause()');check_focus('paused')
   before=page.locator('#homeSeriousModeScreen').bounding_box()
   page.evaluate('stopRestTimerManually()');page.wait_for_timeout(1000)
   after=page.locator('#homeSeriousModeScreen').bounding_box()
   assert before==after,(before,after)
   check_focus('stopped');check_normal()
   assert page.locator('.home-focus-quote-plain').all_text_contents()==order
   assert not errors,errors
   print('PASS focus clipping, quote paint behind mini, normal spacing, timer states, themes and stable order',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
