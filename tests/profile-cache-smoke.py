"""An old full-sync timestamp must not suppress a missing/failed profile read."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text()
needle="get:async(options)=>{calls.push({path,type:'get',source:options?.source});"
assert needle in fixture
fixture=fixture.replace(needle,needle+"if(path==='users/alice/profile/spec'){await new Promise(r=>window.releaseProfile=r);if(window.failProfile)throw Error('unavailable');}",1)
fixture=fixture.replace('  window.fixture={',"  store.set('users/alice/profile/spec',{name:'Verified athlete',height:180,weight:80,age:30});\n  window.fixture={",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');localStorage.setItem('mf_account_v2:alice:mf_full_sync_at_alice',JSON.stringify(Date.now()));window.failProfile=true;")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("typeof releaseProfile==='function'")
 assert page.locator('#settingsHeaderName').inner_text()=='프로필 불러오는 중…'
 assert page.locator('#saveSpecBtn').is_disabled()
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/profile/spec')[0].source")=='server'
 page.evaluate('releaseProfile()')
 page.wait_for_function("profileLoadState==='retry'")
 assert page.evaluate('lsGet("mf_profile_verified_v1",false)') is False
 page.evaluate('window.releaseProfile=null');page.wait_for_function("typeof releaseProfile==='function'")
 page.evaluate('failProfile=false;releaseProfile()')
 page.wait_for_function("profileLoadState==='ready'")
 assert page.locator('#settingsHeaderName').inner_text()=='Verified athlete님'
 assert page.locator('#saveSpecBtn').is_enabled()
 assert page.evaluate('lsGet("mf_profile_verified_v1",false)') is True
 assert not errors,errors
 print('PASS: old fresh timestamp cannot skip missing profile; failed first server read retries; only verified response applies name and enables save without navigation')
 b.close()
