"""Focus quotes shuffle once per page start and remain stable throughout the session."""
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
   context.add_init_script("Math.random=()=>Number(localStorage.getItem('fixture_shuffle_random')||'0')")
   page=context.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300)
   order=lambda:page.locator('.home-focus-quote-plain').all_text_contents()
   first=order();expected=sorted(first);assert len(set(first))==len(first)
   page.evaluate('applyHomeMode(true,{animate:false});applyHomeMode(false,{animate:false});applyHomeMode(true,{animate:false})');assert order()==first
   page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(250);page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(250);assert order()==first
   page.evaluate('applySeriousMode(true)');assert page.locator('.home-focus-quote-page:not([hidden])').count()==1;assert page.locator('.home-focus-quote-original').is_visible()
   page.evaluate('applySeriousMode(false)');assert page.locator('.home-focus-quote-page:not([hidden])').count()==len(expected);assert order()==first
   page.evaluate("localStorage.setItem('fixture_shuffle_random','.75')");page.reload();page.wait_for_timeout(1300);second=order();assert second!=first and sorted(second)==expected
   page.evaluate('applyHomeMode(false,{animate:false});applyHomeMode(true,{animate:false})');assert order()==second
   print('PASS boot shuffle, stable mode/tab returns, full quote set and serious mode',width);context.close()
  browser.close()
finally:server.terminate();server.wait()
