"""Opt-in authentication diagnostics with isolated Firebase only."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(1200)
 assert page.evaluate("localStorage.getItem('mf_login_diagnostic_v1')") is None
 page.evaluate("document.getElementById('loginDiagnosticToggle').click()")
 assert 'ON' in page.locator('#loginDiagnosticToggle').inner_text()
 page.evaluate("()=>{auth.signInWithPopup=()=>new Promise((r,j)=>{window.popupResolve=r;window.popupReject=j;});openLoginSheet();doGoogleLogin();}")
 report=page.evaluate('loginDiagnostic.report()');assert 'popup_start' in report and 'login_click' in report
 page.evaluate("popupReject({code:'auth/popup-closed-by-user',message:'secret@example.test'})");page.wait_for_timeout(100)
 report=page.evaluate('loginDiagnostic.report()');assert 'popup_error' in report and 'auth/popup-closed-by-user' in report and 'secret@example.test' not in report
 page.reload();page.wait_for_timeout(1200)
 report=page.evaluate('loginDiagnostic.report()');assert '실행 2' in report and 'popup_start' in report and 'auth_state' in report
 page.evaluate("document.getElementById('loginDiagnosticCopy').click()");page.wait_for_timeout(100)
 assert 'popup_error' in page.locator('#loginDiagnosticReport').input_value()
 page.evaluate("document.getElementById('loginDiagnosticToggle').click()")
 assert page.evaluate("localStorage.getItem('mf_login_diagnostic_v1')") is None
 assert not errors,errors
 print('PASS: diagnostic OFF by default, stages/errors captured without email, preserved across restart, copy fallback, OFF clears trace')
 b.close()
