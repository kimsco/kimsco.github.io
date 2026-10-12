"""Isolated Firebase popup completion and stalled-login UI checks."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("(()=>{const timeout=window.setTimeout;window.setTimeout=function(fn,ms,...args){return timeout(fn,ms===15000?250:ms,...args);};})()")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];dialogs=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:(dialogs.append(d.message),d.dismiss()))
 page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(1200)
 page.evaluate("""()=>{window.loginCalls=0;auth.signInWithPopup=()=>{loginCalls++;return new Promise((resolve,reject)=>{window.loginResolve=resolve;window.loginReject=reject;});};openLoginSheet();doGoogleLogin();doGoogleLogin();}""")
 assert page.evaluate('loginCalls')==1
 assert page.locator('#loginSheetGoogleBtn').is_disabled()
 assert page.locator('#loginSheet').get_attribute('aria-hidden')=='false'
 page.wait_for_timeout(350)
 assert page.locator('#googleLoginRecover').count()==0
 assert '지연' in page.locator('#googleLoginStatus').inner_text()
 page.evaluate("loginReject({code:'auth/popup-closed-by-user'})");page.wait_for_timeout(100)
 assert page.locator('#loginSheetGoogleBtn').is_enabled()
 assert '취소' in page.locator('#googleLoginStatus').inner_text()
 page.evaluate("""()=>{doGoogleLogin();auth.currentUser={uid:'alice',email:'alice@example.test',displayName:'Alice'};appSync.account.select('alice','alice@example.test');loginResolve({user:auth.currentUser});}""")
 page.wait_for_timeout(500)
 assert page.locator('#settingsLoginRow').is_hidden()
 assert page.locator('#loginSheet').get_attribute('aria-hidden')=='true'
 assert page.evaluate('googleLoginFlow.busy') is False
 assert page.evaluate('loginCalls')==2
 # Poll confirmed SDK state even if neither the popup promise nor a focus event arrives.
 page.evaluate("""()=>{auth.currentUser=null;doGoogleLogin();auth.currentUser={uid:'alice',email:'alice@example.test',displayName:'Alice'};}""")
 page.wait_for_timeout(700)
 assert page.evaluate('googleLoginFlow.busy') is False
 assert page.evaluate('googleLoginPollTimer') is None
 page.evaluate("loginReject({code:'auth/cancelled-popup-request'})");page.wait_for_timeout(100)
 assert not dialogs,dialogs
 assert not errors,errors
 print('PASS: one popup, pending/slow/canceled UI, popup-result success, automatic currentUser reconciliation without focus events, late conflict ignored, no alerts')
 b.close()
