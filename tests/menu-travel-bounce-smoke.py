"""Measure real card-opening keyframes, including screen-edge-capped overshoot."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8239','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,393,430]:
   context=browser.new_context(viewport={'width':width,'height':852},is_mobile=True,has_touch=True,service_workers='block')
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8239');page.wait_for_timeout(1800)
   page.evaluate('applyMenuV2(true);openNavDrawer()');page.wait_for_timeout(420)
   near=far=0
   for key in ['pr3','calc','today']:
    frames=page.evaluate('''key=>{openMenuCalculatorTile(calcTiles[key]);return {frames:menuCalculatorMotion.effect.getKeyframes(),duration:menuCalculatorMotion.effect.getTiming().duration,w:navDrawer.clientWidth,h:navDrawer.clientHeight};}''',key)
    assert frames['duration']==430
    f=frames['frames'];assert len(f)==4
    for axis in ['left','top']:
     start=float(f[1][axis][:-2]);target=float(f[3][axis][:-2]);peak=float(f[2][axis][:-2])
     old=max(4,start+(target-start)*1.0978)
     if abs(target-start)<=96:
      assert abs(peak-old)<.001,(key,axis,peak,old);near+=1
     elif abs(target-start)>=160:
      assert abs((peak-target)-(old-target)/2)<.001,(key,axis,peak,old,target);far+=1
    peak=f[2]
    assert float(peak['left'][:-2])+float(peak['width'][:-2])<=frames['w']-4+.01
    assert float(peak['top'][:-2])+float(peak['height'][:-2])<=frames['h']-4+.01
    page.wait_for_timeout(850)
    assert page.locator('#'+{'pr3':'navThreeSummaryBtn','calc':'navOneRMCalcBtn','today':'navTodayRecordsOpen'}[key]).get_attribute('role')=='dialog'
    page.evaluate('closeMenuCalculator()');page.wait_for_timeout(420)
   assert near and far and not errors,(near,far,errors)
   print('PASS nearby unchanged, distant half bounce, bounded peak and all three cards open/close',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
