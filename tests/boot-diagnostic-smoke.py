"""Opt-in local startup timing diagnostics; never connects to production Firebase."""
"""Web startup layout checks; iOS native launch transitions require a real device."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
fixture=(ROOT/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])

 c=b.new_context(viewport={'width':390,'height':844})
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(1200)
 assert page.locator('#mfBootDiagnosticPanel').count()==0
 page.evaluate("document.getElementById('bootDiagnosticToggle').click()")
 page.reload(wait_until='domcontentloaded')
 assert page.locator('#mfBootDiagnosticPanel').is_visible()
 page.wait_for_timeout(4200)
 data=page.evaluate("JSON.parse(localStorage.getItem('mf_boot_diagnostic_last'))")
 names=[e['name'] for e in data['events']]
 assert all(e in names for e in ['HEAD','SPLASH_DOM','RAF_1','RAF_2','DOM_READY','FADE_START','SPLASH_END']),names
 assert page.locator('#bootSplash').count()==0
 page.evaluate("document.getElementById('bootDiagnosticToggle').click()")
 assert page.locator('#mfBootDiagnosticPanel').count()==0
 page.reload();page.wait_for_timeout(1200)
 assert page.locator('#mfBootDiagnosticPanel').count()==0
 assert page.evaluate("localStorage.getItem('mf_boot_diagnostic_last')") is None
 assert not errors,errors
 print('PASS: startup diagnostics default OFF, enabled across PWA reload, lifecycle timings captured, OFF removes panel and local log')
 b.close()
