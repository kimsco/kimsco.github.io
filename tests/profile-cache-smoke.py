"""An old full-sync timestamp must not suppress a missing/failed profile read."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text()
needle="get:async(options)=>{calls.push({path,type:'get',source:options?.source});"
assert needle in fixture
fixture=fixture.replace(needle,needle+"if(path==='users/alice/profile/spec'){await new Promise(r=>window.releaseProfile=r);if(window.failProfile)throw Error('unavailable');}",1)
fixture=fixture.replace('uid,email:uid+',"uid,getIdToken:async()=> 'isolated-profile-token',email:uid+",1)
fixture=fixture.replace('  window.fixture={',"  store.set('users/alice/profile/spec',{name:'Verified athlete',height:180,weight:80,age:30});\n  window.fixture={",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');localStorage.setItem('mf_account_v2:alice:mf_full_sync_at_alice',JSON.stringify(Date.now()));window.failProfile=true;")
 def route(r):
  if r.request.url.startswith('https://firestore.googleapis.com/v1/'):
   assert r.request.headers.get('authorization')=='Bearer isolated-profile-token'
   r.fulfill(content_type='application/json',body=json.dumps({'fields':{'name':{'stringValue':'Verified athlete'},'height':{'integerValue':'180'},'weight':{'integerValue':'80'},'age':{'integerValue':'30'}}}))
  else:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript')
 c.route('https://**/*',route)
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("typeof releaseProfile==='function'")
 assert page.locator('#settingsHeaderName').inner_text()=='프로필 불러오는 중…'
 assert page.locator('#saveSpecBtn').is_disabled()
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/profile/spec')[0].source")=='server'
 assert page.evaluate('lsGet("mf_profile_verified_v1",false)') is False
 page.evaluate('releaseProfile()')
 page.wait_for_function("profileLoadState==='ready'")
 assert page.locator('#settingsHeaderName').inner_text()=='Verified athlete님'
 assert page.locator('#saveSpecBtn').is_enabled()
 assert page.evaluate('lsGet("mf_profile_verified_v1",false)') is True
 assert not errors,errors
 print('PASS: old fresh timestamp cannot skip missing profile; failed SDK read uses authenticated REST fallback; only verified response applies name and enables save without navigation')
 b.close()
