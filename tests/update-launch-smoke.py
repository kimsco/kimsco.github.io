"""An older loaded document stays open; the next navigation uses the new build."""
from pathlib import Path
import re, subprocess, sys, time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen([sys.executable,'-m','http.server','8198','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 html=(root/'index.html').read_text()
 version=re.search(r'const APP_VERSION = "([^"]+)"',html)[1]
 old=html.replace(f'const APP_VERSION = "{version}"','const APP_VERSION = "0.0.0"')
 fixture=(root/'tests/firebase-fixture.js').read_text()
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for light in [False,True]:
   context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,service_workers='block')
   context.add_init_script("localStorage.setItem('mf_light_mode','"+('1' if light else '0')+"')")
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   documents=[];checks=[]
   def shell(route):
    if route.request.resource_type=='document':
     documents.append(route.request.url)
     route.fulfill(body=old if len(documents)==1 else html,content_type='text/html')
    else:
     checks.append(route.request.url)
     route.fulfill(body=html,content_type='text/html')
   context.route('http://127.0.0.1:8198/',shell)
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8198/');page.wait_for_timeout(1800)
   assert len(documents)==1 and not checks,(documents,checks)
   assert page.locator('#bootSplash').count()==0
   assert page.locator('#appVersionDisplay').text_content().strip()=='0.0.0'
   page.evaluate("window.__launchMarker='preserved';document.querySelector('.app').scrollTop=100")
   page.wait_for_timeout(700)
   assert page.evaluate('window.__launchMarker')=='preserved'
   page.goto('http://127.0.0.1:8198/');page.wait_for_timeout(1400)
   assert len(documents)==2 and not checks,(documents,checks)
   assert page.locator('#appVersionDisplay').text_content().strip()==version
   assert page.locator('#bootSplash').count()==0
   assert not errors,errors
   context.close()
  browser.close()
 print('PASS: dark/light older launch has one splash and no forced reload; next navigation loads current version')
finally:
 server.terminate();server.wait()
