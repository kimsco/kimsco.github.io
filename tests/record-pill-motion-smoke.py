"""Record input pill expansion threshold and interruption behavior; fake Firebase."""
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
   page.evaluate("""()=>{window.testScroll=document.createElement('div');testScroll.style.cssText='position:fixed;top:0;left:0;width:200px;height:100px;overflow:auto';testScroll.innerHTML='<div style="height:2000px"></div>';document.body.append(testScroll);window.testBar=document.createElement('div');testBar.style.cssText='position:fixed;top:200px;left:10px;width:200px;height:50px;transform:scale(1)';testBar.innerHTML='<input type="text">';document.body.append(testBar);window.testController=wireFloatingSaveBar(testBar,[testScroll]);}""")
   def scroll(y,wait=40):
    page.evaluate('(y)=>testScroll.scrollTop=y',y);page.wait_for_timeout(wait)
   def scale():return page.evaluate('new DOMMatrixReadOnly(getComputedStyle(testBar).transform).m11')
   scroll(200,650);assert abs(scale()-.8)<.01
   scroll(194);assert abs(scale()-.8144)<.01,scale()
   scroll(188);assert abs(scale()-.8288)<.01
   scroll(176);assert abs(scale()-.8576)<.01
   scroll(170);assert abs(scale()-.872)<.01
   scroll(164,20);assert page.evaluate('testBar.style.transform')=='scale(1)'
   scroll(160,20);assert scale()<1.04
   frames=page.evaluate("""async()=>{const values=[];for(let i=0;i<40;i++){await new Promise(requestAnimationFrame);values.push(new DOMMatrixReadOnly(getComputedStyle(testBar).transform).m11);}return values;}""")
   assert 1.00001<max(frames)<1.01,max(frames)
   assert abs(scale()-1)<.001
   scroll(234,650);assert abs(scale()-.8)<.01
   scroll(198,30);before=scale();scroll(210,20);assert abs(scale()-before)<.08,(before,scale())
   page.evaluate('testBar.querySelector("input").focus()');page.wait_for_timeout(300);assert abs(scale()-1)<.001
   scroll(280,300);page.evaluate('testController.reset()');assert abs(scale()-1)<.001
   # Collapse mirrors expansion: small proportional changes, then a slight undershoot.
   scroll(300,650);page.evaluate('testController.reset()')
   scroll(306);assert abs(scale()-.9856)<.01
   scroll(324);assert abs(scale()-.9424)<.01
   before=scale();scroll(336,80);assert page.evaluate('testBar.style.transform')=='scale(0.8)'
   assert before-scale()<.035,(before,scale())
   scroll(340,20)
   frames=page.evaluate("""async()=>{const out=[];for(let i=0;i<48;i++){await new Promise(requestAnimationFrame);out.push(new DOMMatrixReadOnly(getComputedStyle(testBar).transform).m11);}return out;}""")
   assert .79<min(frames)<.79999,min(frames)
   assert abs(scale()-.8)<.001
   # Reverse a collapsing spring without jumping to its destination first.
   page.evaluate('testController.reset()');scroll(376,30);before=scale();scroll(370,20)
   assert abs(scale()-before)<.08,(before,scale())
   page.evaluate('testController.reset()')
   # First touch on any collapsed control expands only, including the save button.
   page.evaluate("document.activeElement.blur();testBar.querySelector('input').style.width='100px';window.saveClicks=0;const button=document.createElement('button');button.textContent='저장';button.onclick=()=>saveClicks++;testBar.append(button);")
   scroll(500,700);assert abs(scale()-.8)<.01
   page.locator('body > div input').last.tap();page.wait_for_timeout(600)
   assert abs(scale()-1)<.001 and not page.evaluate("testBar.contains(document.activeElement)")
   page.locator('body > div input').last.tap();assert page.evaluate("document.activeElement===testBar.querySelector('input')")
   page.evaluate('document.activeElement.blur()');scroll(560,700)
   page.locator('body > div button').last.tap();assert page.evaluate('saveClicks')==0
   page.wait_for_timeout(600);assert abs(scale()-1)<.001
   page.locator('body > div button').last.tap();assert page.evaluate('saveClicks')==1
   page.evaluate('testController.reset()')
   scroll(394,100);page.evaluate('testController.reset()')
   page.emulate_media(reduced_motion='reduce');scroll(430);assert abs(scale()-.8)<.001
   scroll(394);assert abs(scale()-1)<.001
   print('PASS: symmetric proportional growth/shrink, 36px springs with restrained overshoot/undershoot, continued scroll, reversal, focus/reset and reduced motion')
   c.close()
  b.close()
finally:server.terminate();server.wait()
