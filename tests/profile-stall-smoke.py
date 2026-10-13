"""A never-resolving SDK read recovers independently, with no tab navigation."""
from pathlib import Path
import json,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
needle="get:async(options)=>{calls.push({path,type:'get',source:options?.source});"
assert needle in fixture
fixture=fixture.replace(needle,needle+"if(path==='users/alice/profile/spec')await new Promise(r=>window.releaseStalledProfile=r);",1)
fixture=fixture.replace('uid,email:uid+',"uid,getIdToken:async()=> 'isolated-profile-token',email:uid+",1)
fixture=fixture.replace('  window.fixture={',"  store.set('users/alice/profile/spec',{name:'Old SDK response'});\n  window.fixture={",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148')
 c.add_init_script("Object.defineProperty(navigator,'standalone',{value:true});localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 rest=[]
 def route(r):
  if r.request.url.startswith('https://firestore.googleapis.com/v1/'):
   assert r.request.url.endswith('/documents/users/alice/profile/spec')
   assert r.request.headers.get('authorization')=='Bearer isolated-profile-token'
   rest.append(r.request.url)
   r.fulfill(content_type='application/json',body=json.dumps({'fields':{'name':{'stringValue':'Recovered athlete'},'height':{'integerValue':'180'},'weight':{'integerValue':'80'},'age':{'integerValue':'30'}}}))
  else:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript')
 c.route('https://**/*',route)
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("typeof releaseStalledProfile==='function'")
 assert page.locator('#settingsHeaderName').inner_text()=='프로필 불러오는 중…'
 started=time.monotonic();page.wait_for_function("profileLoadState==='ready'",timeout=7000)
 assert time.monotonic()-started<6
 assert page.locator('#settingsHeaderName').inner_text()=='Recovered athlete님'
 assert len(rest)==1
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/profile/spec').length")==1
 page.evaluate('releaseStalledProfile()');page.wait_for_timeout(150)
 assert page.locator('#settingsHeaderName').inner_text()=='Recovered athlete님'
 assert page.locator('#specName').input_value()=='Recovered athlete'
 assert page.evaluate('calcTargets(userSpec).targetCalories')>0
 assert not errors,errors
 print('PASS: iPhone standalone runtime recovers a never-resolving SDK profile read via one authenticated REST read without navigation; late SDK result cannot overwrite it')
 b.close()
