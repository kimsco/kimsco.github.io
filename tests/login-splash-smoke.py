"""One-shot login splash suppression, using isolated Firebase."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/',wait_until='domcontentloaded');assert page.locator('#bootSplash').is_visible();page.wait_for_timeout(1200)
 page.evaluate('openSettingsBtn.click()');page.wait_for_timeout(300)
 with page.expect_navigation(wait_until='domcontentloaded'):
  page.evaluate("""()=>{auth.signInWithPopup=async()=>{localStorage.setItem('fixture_uid','alice');auth.currentUser={uid:'alice',email:'alice@example.test',displayName:'Alice'};return {user:auth.currentUser};};doGoogleLogin();}""")
 assert page.evaluate('window.__skipLoginSplash') is True
 assert page.locator('#bootSplash').count()==0
 assert page.evaluate("sessionStorage.getItem('mf_skip_login_splash')") is None
 page.wait_for_timeout(500)
 assert not page.locator('#settingsOverlay').evaluate("e=>e.classList.contains('hidden')")
 assert page.locator('#settingsLoginRow').is_hidden()
 assert page.evaluate('appSync.account.owner')=='alice'
 page.reload(wait_until='domcontentloaded')
 assert page.evaluate('window.__skipLoginSplash') is False
 assert page.locator('#bootSplash').is_visible()
 page.wait_for_timeout(1200)
 page.evaluate("sessionStorage.setItem('mf_skip_login_splash',String(Date.now()-120000))")
 page.reload(wait_until='domcontentloaded')
 assert page.locator('#bootSplash').is_visible()
 page.evaluate("sessionStorage.setItem('mf_skip_login_splash',String(Date.now()))")
 page.goto('http://127.0.0.1:8000/?fresh=1',wait_until='domcontentloaded')
 assert page.evaluate('window.__skipLoginSplash') is False
 assert page.locator('#bootSplash').is_visible()
 assert not errors,errors
 print('PASS: normal startup logo retained, confirmed login account reload skips logo once and keeps settings, consumed/expired flags cannot suppress future startup')
 b.close()
