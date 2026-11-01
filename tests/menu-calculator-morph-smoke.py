"""Calculator tile morph, shared controls, results, reversal and lifecycle cleanup."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8232','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   c=b.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8232');page.wait_for_timeout(1600)
   page.evaluate('applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(400)
   assert page.locator('#navToolsLabel').is_hidden()
   page.evaluate('window.originalCalculatorCard=document.getElementById("navOneRMCalcBtn")')
   assert page.locator('#menuCalculator').count()==0
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light);page.wait_for_timeout(250)
    button=page.locator('#navOneRMCalcBtn');start=button.bounding_box()
    source_color=button.evaluate('e=>getComputedStyle(e).backgroundColor')
    heading=page.locator('#navMenuTitle').bounding_box()
    routine=page.locator('#navMyRoutineBtn').bounding_box()
    page.evaluate("window.calculatorBounds=[];window.captureCalculator=true;requestAnimationFrame(function capture(){if(!window.captureCalculator)return;const e=document.getElementById('navOneRMCalcBtn');if(e.classList.contains('calculator-expanded')){const r=e.getBoundingClientRect();calculatorBounds.push({bottom:r.bottom,width:r.width,height:r.height});}requestAnimationFrame(capture);});")
    button.click();page.wait_for_timeout(80)
    assert page.locator('#navMenuBody').evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.locator('#navMenuTitle').bounding_box()==heading
    assert page.locator('#navMyRoutineBtn').bounding_box()==routine
    early=page.locator('#navOneRMCalcBtn').bounding_box()
    assert early['width']>start['width'] and early['y']<start['y'],(start,early)
    motion=page.evaluate("()=>{const m=menuCalculatorMotion,f=m.effect.getKeyframes();return {duration:m.effect.getTiming().duration,frames:f.length};}")
    assert motion=={'duration':430,'frames':2},motion
    content_bounds=page.evaluate("()=>{const c=menuCalculator.getBoundingClientRect(),i=document.getElementById('weight').getBoundingClientRect();return {left:c.left,right:c.right,inputLeft:i.left,inputRight:i.right};}")
    assert content_bounds['inputLeft']>=content_bounds['left']+20 and content_bounds['inputRight']<=content_bounds['right']-20,content_bounds
    assert page.locator('#menuCalculatorGhost .nav-menu-copy').count()==1
    assert page.locator('#menuCalculatorTitle').evaluate('e=>getComputedStyle(e).clipPath')=='inset(50%)'
    assert page.locator('#menuCalculatorGhost .nav-menu-copy>span').first.evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.evaluate('menuCalculator===window.originalCalculatorCard && document.getElementById("navOneRMCalcBtn")===window.originalCalculatorCard')
    colors=page.evaluate('menuCalculatorMotion.effect.getKeyframes().map(f=>f.backgroundColor)')
    assert colors[0]==source_color and colors[0]!=colors[-1],colors
    current_color=button.evaluate('e=>getComputedStyle(e).backgroundColor')
    assert current_color not in [colors[0],colors[-1]],(current_color,colors)
    fade=page.locator('#menuCalculatorContent').evaluate('e=>Number(getComputedStyle(e).opacity)')
    assert 0<fade<1,fade
    assert page.locator('#menuCalculatorTitle').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')==18
    assert page.locator('#weight').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')==15
    page.wait_for_timeout(240)
    assert page.locator('#menuCalculatorContent').evaluate('e=>Number(getComputedStyle(e).opacity)')>.1
    page.screenshot(path=f'/tmp/menu-calculator-opening-{width}-{light}.png')
    panel=page.locator('#navOneRMCalcBtn');middle=panel.bounding_box()
    assert middle['width']>start['width'] and middle['height']>start['height'],(start,middle)
    assert page.locator('#navDrawerOverlay').is_visible() and page.locator('#oneRMCalcOverlay').is_hidden()
    page.wait_for_timeout(700)
    final=panel.bounding_box();assert final['width']>start['width']*1.9
    label_box=page.locator('#menuCalculatorGhost .nav-menu-copy').bounding_box();back_box=page.locator('#menuCalculatorBack').bounding_box()
    assert abs(label_box['y']+label_box['height']/2-back_box['y']-back_box['height']/2)<1,(label_box,back_box)
    bounds=page.evaluate('window.captureCalculator=false;calculatorBounds')
    assert bounds and max(r['bottom'] for r in bounds)<=825,bounds
    assert all(r['width']>=start['width']*.96 and r['height']>=start['height']*.96 for r in bounds),bounds
    assert all(bounds[i+1]['height']>=bounds[i]['height']-.5 for i in range(len(bounds)-1)),bounds
    if width==390 and not light:
     page.evaluate("window.actualCalculatorViewport=window.visualViewport;Object.defineProperty(window,'visualViewport',{configurable:true,value:{height:500,offsetTop:0}});resizeMenuCalculator();")
     short=panel.bounding_box();assert abs(short['y']+short['height']-480)<1,short
     page.evaluate("Object.defineProperty(window,'visualViewport',{configurable:true,value:window.actualCalculatorViewport});resizeMenuCalculator();")
    first=page.locator('#navThreeSummaryBtn').bounding_box()
    title=page.locator('#navMenuTitle').bounding_box()
    expected_top=(title['y']+title['height']+first['y'])/2
    assert abs(final['y']-expected_top)<1 and abs(final['y']+final['height']-824)<1,final
    assert panel.evaluate('e=>getComputedStyle(e).borderBottomLeftRadius')=='32px'
    assert panel.evaluate('e=>getComputedStyle(e).borderBottomRightRadius')=='32px'
    assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest(".calculator-expanded")')
    assert page.locator('#weight').count()==1 and page.locator('#oneRMCalcDisclaimer').count()==0
    assert page.locator('#navMenuBody').evaluate('e=>e.inert')
    page.locator('#oneRMLiftSelect').select_option('bench');page.locator('#weight').fill('100');page.locator('#reps').select_option('5');page.locator('#goBtn').click()
    assert page.locator('#tableArea>div').count()==12
    expected=page.evaluate('100*NSCA_TABLE.bench[4]')
    assert f'{expected:.1f}kg' in page.locator('#tableArea>div').first.inner_text()
    page.screenshot(path=f'/tmp/menu-calculator-{width}-{light}.png')
    page.evaluate("window.calculatorClosingBounds=[];requestAnimationFrame(function capture(){const e=document.getElementById('navOneRMCalcBtn');if(!e.classList.contains('calculator-expanded'))return;const r=e.getBoundingClientRect();calculatorClosingBounds.push({bottom:r.bottom,height:r.height});requestAnimationFrame(capture);});")
    page.locator('#menuCalculatorBack').click()
    assert page.evaluate('menuCalculatorMotion.effect.getTiming().duration')==330
    page.wait_for_timeout(110)
    assert page.locator('#navMenuBody').evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.locator('#navMyRoutineBtn').bounding_box()==routine
    page.wait_for_timeout(650)
    assert not panel.evaluate('e=>e.classList.contains("calculator-expanded")') and not page.locator('#navMenuBody').evaluate('e=>e.inert')
    closing=page.evaluate('calculatorClosingBounds')
    assert closing and max(r['bottom'] for r in closing)<=825,closing
    assert all(closing[i+1]['height']<=closing[i]['height']+.5 for i in range(len(closing)-1)),closing
    assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#oneRMCalcOverlay")')
    assert button.evaluate('e=>e===window.originalCalculatorCard && !!e.closest("#navMenuBody")')
   # Reverse while opening, then reopen and close the full menu externally.
   button.click();page.wait_for_timeout(90);page.keyboard.press('Escape');page.wait_for_timeout(760)
   assert not panel.evaluate('e=>e.classList.contains("calculator-expanded")') and page.locator('#navDrawerOverlay').is_visible()
   button.click();page.wait_for_timeout(940);page.evaluate('closeNavDrawer()');page.wait_for_timeout(420)
   assert page.locator('#navDrawerOverlay').is_hidden() and not panel.evaluate('e=>e.classList.contains("calculator-expanded")')
   assert page.locator('.app').evaluate('e=>!e.inert&&!e.style.transform&&!e.style.opacity')
   page.evaluate('applyMenuV2(false);openNavDrawer()');page.wait_for_timeout(400)
   button.click();page.wait_for_timeout(150)
   assert page.locator('#oneRMCalcOverlay').is_visible() and page.locator('#navDrawerOverlay').is_hidden()
   assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#oneRMCalcOverlay")')
   page.evaluate('closeOneRMCalc();applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(400)
   page.emulate_media(reduced_motion='reduce');button.click();page.wait_for_timeout(50)
   assert panel.evaluate('e=>e.classList.contains("is-ready")')
   assert not errors,errors
   print('PASS tile morph, results, themes, reversal, cleanup, legacy and reduced motion',width);c.close()
  b.close()
finally:server.terminate();server.wait()
