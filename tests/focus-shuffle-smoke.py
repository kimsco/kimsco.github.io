"""Focus shuffle preserves every quote and the separate serious-mode quote."""
import subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8213','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844});context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300)
   order=lambda:page.locator('.home-focus-quote-plain').all_text_contents()
   expected=sorted(order());page.evaluate('Math.random=()=>0;applyHomeMode(true,{animate:false})');first=order();assert sorted(first)==expected and len(set(first))==len(first)
   page.evaluate('applyHomeMode(true,{animate:false})');assert order()==first
   page.evaluate('applyHomeMode(false,{animate:false});applyHomeMode(true,{animate:false})');second=order();assert second[0]!=first[0] and sorted(second)==expected
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(250);page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(250);third=order();assert third[0]!=second[0] and sorted(third)==expected
   page.evaluate('applySeriousMode(true);applyHomeMode(false,{animate:false});applyHomeMode(true,{animate:false})');assert page.locator('.home-focus-quote-page:not([hidden])').count()==1;assert page.locator('.home-focus-quote-original').is_visible()
   page.evaluate('applySeriousMode(false);applyHomeMode(false,{animate:false});applyHomeMode(true,{animate:false})');assert page.locator('.home-focus-quote-page:not([hidden])').count()==len(expected);assert sorted(order())==expected
   assert page.locator('#homeSeriousModeScreen').evaluate('e=>e.scrollTop')==0
   print('PASS random entry/return order, no repeated first quote, full set and serious mode',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
