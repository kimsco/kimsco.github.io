"""Mobile integration checks with isolated Firebase; TLS-verified Chart.js download.
Run: python3 tests/browser_smoke.py (start Python HTTP server on port 8000 first).
Requires Python Playwright and /usr/bin/chromium; never accesses production user data.
"""
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
chart=urllib.request.urlopen('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',timeout=30).read()
fixture=(ROOT/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    def route(r):
        url=r.request.url
        if '/firebase-app.js' in url:r.fulfill(status=200,content_type='application/javascript',body=fixture)
        elif 'firebasejs/' in url:r.fulfill(status=200,content_type='application/javascript',body='')
        elif 'chart.js' in url:r.fulfill(status=200,content_type='application/javascript',body=chart)
        else:r.abort()
    context.route('https://**/*',route)
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/',wait_until='load');page.wait_for_timeout(300)
    assert not errors,errors
    page.evaluate("localStorage.setItem('mf_rest_timer_enabled','1')")
    page.reload();page.wait_for_timeout(200)
    page.locator('.bottomTab .tabBtn[data-target="tab2"]').click()
    page.locator('#recordWeight').fill('80');page.locator('#recordReps').fill('5');page.locator('#recordAdd').click()
    page.wait_for_timeout(800)
    assert page.evaluate('records.bench.length')==1
    assert page.evaluate('restTimerActive')
    page.evaluate("applyRestTimerState(restStopwatch.reset()); localStorage.setItem(appSync.account.key('mf_rest_stopwatch_v1'),JSON.stringify({active:true,startedAt:Date.now()-65000,pausedAt:0,pausedTotalMs:0}))")
    page.reload();page.wait_for_timeout(300)
    assert page.evaluate('restTimerActive')
    assert page.evaluate('restTimerElapsedMs()')>=65000
    page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(650)
    page.locator('#restTimerPauseBtn').click();paused=page.evaluate('restTimerElapsedMs()')
    page.reload();page.wait_for_timeout(300)
    assert page.evaluate('restTimerPausedAt')>0
    assert page.evaluate('restTimerElapsedMs()')==paused
    for tab in ['tab2','tab1','tab3','tab2','tab1','tab2','tab4','tab1']:
        page.locator(f'.bottomTab .tabBtn[data-target="{tab}"]').click();page.wait_for_timeout(60)
    page.wait_for_timeout(750)
    assert page.locator('#restTimerMiniDisplay').is_visible()
    assert not page.locator('#restTimerMiniPlayIcon').get_attribute('class')=='hidden'
    assert page.evaluate("document.documentElement.classList.contains('rtimer-mini-active')")
    for light in [True,False]:
        page.evaluate('(v)=>applyLightMode(v)',light)
        page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(700)
        assert page.locator('#restTimerDisplay').is_visible()
        geometry=page.evaluate('''() => {const r=restTimerCardBg.getBoundingClientRect();return {w:r.width,h:r.height,x:r.left};}''')
        assert geometry['w']>200 and geometry['h']>20 and geometry['x']>=0,geometry
        page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(700)
        assert page.locator('#restTimerMiniDisplay').is_visible()
    page.evaluate('stopRestTimerManually()');page.wait_for_timeout(900)
    assert page.evaluate("localStorage.getItem(appSync.account.key('mf_rest_stopwatch_v1'))") is None
    assert not page.evaluate('restTimerActive')
    # Signed-in isolated fixture: queue a set offline, restart, retry and delete.
    page.evaluate("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice')")
    page.reload();page.wait_for_timeout(400)
    page.evaluate('fixture.setOnline(false)')
    page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(200)
    page.locator('#recordWeight').fill('90');page.locator('#recordReps').fill('3');page.locator('#recordAdd').click();page.wait_for_timeout(200)
    identity=page.evaluate('records.bench[0].firestoreId')
    assert identity and not identity.startswith('local_')
    assert page.evaluate("Object.keys(appSync.outbox.read('alice').ops).length")>0
    page.reload();page.wait_for_timeout(500)
    assert page.evaluate('(id)=>records.bench.filter(r=>r.firestoreId===id).length',identity)==1
    assert page.evaluate("Object.keys(appSync.outbox.read('alice').ops).length")==0
    page.evaluate('(id)=>deleteRecord(id)',identity);page.wait_for_timeout(200)
    assert page.evaluate('(id)=>fixture.store.has("users/alice/records/"+id)',identity) is False
    assert not errors,errors
    # Restart in a different account: alice data/stopwatch must never appear.
    page.evaluate("localStorage.setItem('fixture_uid','bob')")
    page.reload();page.wait_for_timeout(500)
    assert page.evaluate('appSync.account.owner')=='bob'
    assert page.evaluate('records.bench.length')==0
    page.evaluate('fixture.auth.signOut()');page.wait_for_timeout(500)
    assert page.evaluate('appSync.account.owner')=='guest'
    assert page.evaluate('records.bench.length')==1
    assert not errors,errors
    print('PASS: mobile set/save, offline restart/retry/delete, account change/logout, running/paused reload, 8 rapid tabs, dark/light pill geometry')
    browser.close()
