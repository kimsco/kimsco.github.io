"""Startup updates stay behind the splash; slow/offline checks never reload later."""
from pathlib import Path
import re, subprocess, sys, time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen([sys.executable,'-m','http.server','8198','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 html=(root/'index.html').read_text()
 version=re.search(r'const APP_VERSION = "([0-9.]+)"',html)[1]
 old=html.replace(f'const APP_VERSION = "{version}"','const APP_VERSION = "0.0.0"')
 fixture=(root/'tests/firebase-fixture.js').read_text()
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for scenario in ['fresh','update','offline','slow','stale_redirect','storage_blocked']:
   context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,service_workers='block')
   context.add_init_script("localStorage.setItem('mf_light_mode','1')")
   if scenario=='storage_blocked':
    context.add_init_script("const storeItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key==='mf_startup_update')throw new Error('disabled');return storeItem.call(this,key,value)}")
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   documents=[];checks=[];exposed=[]
   context.expose_binding('reportOldHome',lambda source:exposed.append(True))
   context.add_init_script("""requestAnimationFrame(function inspect(){const tab=document.getElementById('tab1'),version=document.getElementById('appVersionDisplay');if(tab && version && version.textContent.trim()==='0.0.0' && getComputedStyle(tab).visibility==='visible')window.reportOldHome();requestAnimationFrame(inspect);});""")
   def shell(route):
    if route.request.resource_type=='document':
     documents.append(route.request.url)
     body=html if scenario=='fresh' or (len(documents)>1 and scenario!='stale_redirect') else old
     route.fulfill(body=body,content_type='text/html')
    else:
     checks.append(route.request.url)
     if scenario in ['offline','slow']:route.abort()
     else:route.fulfill(body=html,content_type='text/html')
   context.route(re.compile(r'http://127\.0\.0\.1:8198/(?:index\.html)?(?:\?.*)?$'),shell)
   if scenario=='slow':
    context.add_init_script("""const originalFetch=window.fetch.bind(window);window.fetch=(url,options)=>String(url).includes('startup_check=')?new Promise(resolve=>setTimeout(()=>resolve(new Response('const APP_VERSION = "999.0.0";')),2000)):originalFetch(url,options);""")
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8198/');page.wait_for_timeout(2600)
   updates=scenario in ['update','stale_redirect']
   assert len(documents)==(2 if updates else 1),(scenario,documents)
   assert len(checks)==(0 if scenario=='slow' else 1),(scenario,checks)
   assert page.locator('#bootSplash').count()==0,scenario
   expected=version if scenario in ['fresh','update'] else '0.0.0'
   assert page.locator('#appVersionDisplay').text_content().strip()==expected,scenario
   if scenario=='update':assert not exposed,exposed
   assert 'app_update' not in page.url,page.url
   count=len(documents)
   page.evaluate("window.__launchMarker='preserved';document.querySelector('.app').scrollTop=100")
   page.wait_for_timeout(500)
   assert page.evaluate('window.__launchMarker')=='preserved' and len(documents)==count,scenario
   assert not errors,(scenario,errors)
   context.close()
  browser.close()
 print('PASS: startup update before home, fresh/offline/slow paths, no late reload, stale redirect loop guard and unavailable storage')
finally:
 server.terminate();server.wait()
