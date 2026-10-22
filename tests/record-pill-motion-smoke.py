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
   scroll(200,300);assert abs(scale()-.8)<.01
   scroll(194);assert abs(scale()-.824)<.01,scale()
   scroll(188);assert abs(scale()-.848)<.01
   scroll(176);assert abs(scale()-.896)<.01
   scroll(170,20);assert page.evaluate('testBar.style.transform')=='scale(1)'
   scroll(166,20);assert scale()<1.04
   page.wait_for_timeout(600);assert abs(scale()-1)<.001
   scroll(234,300);assert abs(scale()-.8)<.01
   scroll(204,30);before=scale();scroll(210,20);assert abs(scale()-before)<.08,(before,scale())
   page.evaluate('testBar.querySelector("input").focus()');page.wait_for_timeout(300);assert abs(scale()-1)<.001
   scroll(280,300);page.evaluate('testController.reset()');assert abs(scale()-1)<.001
   page.emulate_media(reduced_motion='reduce');scroll(350);assert abs(scale()-.8)<.001
   scroll(320);assert abs(scale()-1)<.001
   print('PASS: proportional shrink, initial proportional expansion, 30px spring trigger, continued scroll, reversal, focus/reset and reduced motion')
   c.close()
  b.close()
finally:server.terminate();server.wait()
