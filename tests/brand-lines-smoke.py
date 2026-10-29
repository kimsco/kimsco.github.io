"""Narrative text stays on authored lines at mobile widths."""
import subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8213','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   context=browser.new_context(viewport={'width':width,'height':844});context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();page.goto('http://127.0.0.1:8213');page.wait_for_timeout(1300);page.evaluate('openWhoFor()')
   metrics=page.locator('.who-fit-line').evaluate_all('es=>es.map(e=>({text:e.textContent,w:e.clientWidth,sw:e.scrollWidth,font:getComputedStyle(e).fontSize}))');bad=[x for x in metrics if x['sw']>x['w']+1];assert not bad,bad
   assert page.locator('#whoForCtaMain').inner_text()=='TO THE TOP'
   assert page.locator('.who-chapter-body p').first.locator('.who-fit-line').count()==1
   assert page.locator('.who-chapter-body p').nth(2).locator('.who-fit-line').count()==4
   for step in [1,3,6,7]:
    page.evaluate('(n)=>{whoForTrack.style.transition="none";whoForTrack.style.transform=`translateY(-${n*100}dvh)`}',step);page.screenshot(path=f'/tmp/brand-fit-{width}-{step}.png')
   page.set_viewport_size({'width':375,'height':844});page.wait_for_timeout(100);assert page.locator('.who-fit-line').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)')
   page.evaluate('whoForPlayCtaIntro()');page.wait_for_timeout(3000);assert page.evaluate('whoForCtaReady');page.evaluate('closeWhoFor()');assert page.locator('#whoForOverlay').is_hidden()
   print('PASS narrative lines, authored breaks, resize and final animation/punctuation',width,min(float(x['font'].replace('px','')) for x in metrics));context.close()
  browser.close()
finally:server.terminate();server.wait()
