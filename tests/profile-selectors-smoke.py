"""Isolated checks for matching, sliding profile selectors."""
import subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8213','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1200);page.evaluate('openMySpec()');page.wait_for_timeout(400)
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light)
    for kind,values in [('gender',['female','male']),('goal',['bulk','cut','maintain'])]:
     for value in values:
      result=page.evaluate('''async ([kind,value])=>{
        const indicator=document.getElementById(kind+'ToggleIndicator');
        const before=new DOMMatrix(getComputedStyle(indicator).transform).m41;
        document.querySelector(`.${kind}Btn[data-${kind}="${value}"]`).click();
        await new Promise(r=>setTimeout(r,90));
        const mid=new DOMMatrix(getComputedStyle(indicator).transform).m41;
        const labelOffset=new DOMMatrix(getComputedStyle(indicator.firstElementChild).transform).m41;
        await new Promise(r=>setTimeout(r,300));
        const btn=document.querySelector(`.${kind}Btn.active`);
        return {before,mid,labelOffset,end:new DOMMatrix(getComputedStyle(indicator).transform).m41,target:btn.offsetLeft,width:indicator.offsetWidth,buttonWidth:btn.offsetWidth,color:getComputedStyle(btn).color};
      }''',[kind,value])
      assert abs(result['end']-result['target'])<1,result
      assert result['width']==result['buttonWidth'],result
      assert abs(result['mid']+result['labelOffset'])<1,result
      if abs(result['before']-result['end'])>1:assert min(result['before'],result['end'])<result['mid']<max(result['before'],result['end']),result
    assert page.locator('#genderToggleIndicator').evaluate('e=>getComputedStyle(e).backgroundColor')==page.locator('#goalToggleIndicator').evaluate('e=>getComputedStyle(e).backgroundColor')
    assert page.locator('.genderBtn.active').evaluate('e=>getComputedStyle(e).color')==page.locator('.goalBtn.active').evaluate('e=>getComputedStyle(e).color')
    assert page.locator('#genderToggleIndicator').evaluate('e=>getComputedStyle(e).opacity')=='1'
   page.screenshot(path=f'/tmp/profile-label-fix-{width}.png')
   page.evaluate('closeMySpec()');page.wait_for_timeout(400);page.evaluate('openMySpec()');page.wait_for_timeout(400)
   assert page.locator('.goalBtn.active').get_attribute('data-goal')=='maintain'
   page.emulate_media(reduced_motion='reduce');assert page.locator('#goalToggleIndicator').evaluate('e=>getComputedStyle(e).transitionDuration')=='0s'
   print('PASS sliding geometry, matching colors, reopen and reduced motion',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
