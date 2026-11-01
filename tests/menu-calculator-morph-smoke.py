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
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    button=page.locator('#navOneRMCalcBtn');start=button.bounding_box()
    heading=page.locator('#navMenuTitle').bounding_box()
    routine=page.locator('#navMyRoutineBtn').bounding_box()
    page.evaluate("window.calculatorBounds=[];window.captureCalculator=true;requestAnimationFrame(function capture(){if(!window.captureCalculator)return;const e=document.getElementById('menuCalculator');if(!e.classList.contains('hidden')){const r=e.getBoundingClientRect();calculatorBounds.push({bottom:r.bottom,width:r.width,height:r.height});}requestAnimationFrame(capture);});")
    button.click();page.wait_for_timeout(80)
    assert page.locator('#navMenuBody').evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.locator('#navMenuTitle').bounding_box()==heading
    assert page.locator('#navMyRoutineBtn').bounding_box()==routine
    early=page.locator('#menuCalculator').bounding_box()
    assert early['width']<start['width'] and early['y']>start['y'],(start,early)
    motion=page.evaluate("()=>{const m=menuCalculatorMotion,f=m.effect.getKeyframes();return {duration:m.effect.getTiming().duration,beanWidth:parseFloat(f[1].width),beanHeight:parseFloat(f[1].height)};}")
    assert motion=={'duration':430,'beanWidth':72,'beanHeight':40},motion
    page.wait_for_timeout(240)
    assert page.locator('#menuCalculatorContent').evaluate('e=>Number(getComputedStyle(e).opacity)')>.1
    page.screenshot(path=f'/tmp/menu-calculator-opening-{width}-{light}.png')
    panel=page.locator('#menuCalculator');middle=panel.bounding_box()
    assert middle['width']>start['width'] and middle['height']>start['height'],(start,middle)
    assert page.locator('#navDrawerOverlay').is_visible() and page.locator('#oneRMCalcOverlay').is_hidden()
    page.wait_for_timeout(700)
    final=panel.bounding_box();assert final['width']>start['width']*1.9
    bounds=page.evaluate('window.captureCalculator=false;calculatorBounds')
    assert bounds and max(r['bottom'] for r in bounds)<=845,bounds
    assert any(r['width']<100 and r['height']<60 for r in bounds),bounds
    if width==390 and not light:
     page.evaluate("window.actualCalculatorViewport=window.visualViewport;Object.defineProperty(window,'visualViewport',{configurable:true,value:{height:500,offsetTop:0}});resizeMenuCalculator();")
     short=panel.bounding_box();assert abs(short['y']+short['height']-500)<1,short
     page.evaluate("Object.defineProperty(window,'visualViewport',{configurable:true,value:window.actualCalculatorViewport});resizeMenuCalculator();")
    first=page.locator('#navThreeSummaryBtn').bounding_box()
    title=page.locator('#navMenuTitle').bounding_box()
    expected_top=(title['y']+title['height']+first['y'])/2
    assert abs(final['y']-expected_top)<1 and abs(final['y']+final['height']-844)<1,final
    assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#menuCalculator")')
    assert page.locator('#weight').count()==1 and page.locator('#oneRMCalcDisclaimer').count()==0
    assert page.locator('#navMenuBody').evaluate('e=>e.inert')
    page.locator('#oneRMLiftSelect').select_option('bench');page.locator('#weight').fill('100');page.locator('#reps').select_option('5');page.locator('#goBtn').click()
    assert page.locator('#tableArea>div').count()==12
    expected=page.evaluate('100*NSCA_TABLE.bench[4]')
    assert f'{expected:.1f}kg' in page.locator('#tableArea>div').first.inner_text()
    page.screenshot(path=f'/tmp/menu-calculator-{width}-{light}.png')
    page.locator('#menuCalculatorBack').click()
    assert page.evaluate('menuCalculatorMotion.effect.getTiming().duration')==330
    page.wait_for_timeout(110)
    assert page.locator('#navMenuBody').evaluate('e=>getComputedStyle(e).opacity')=='1'
    assert page.locator('#navMyRoutineBtn').bounding_box()==routine
    page.wait_for_timeout(650)
    assert panel.is_hidden() and not page.locator('#navMenuBody').evaluate('e=>e.inert')
    assert page.locator('#oneRMCalcBody').evaluate('e=>!!e.closest("#oneRMCalcOverlay")')
   # Reverse while opening, then reopen and close the full menu externally.
   button.click();page.wait_for_timeout(90);page.keyboard.press('Escape');page.wait_for_timeout(760)
   assert panel.is_hidden() and page.locator('#navDrawerOverlay').is_visible()
   button.click();page.wait_for_timeout(940);page.evaluate('closeNavDrawer()');page.wait_for_timeout(420)
   assert page.locator('#navDrawerOverlay').is_hidden() and panel.is_hidden()
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
