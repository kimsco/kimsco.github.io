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
    assert page.locator('#syncStatus').is_hidden()
    page.evaluate('fixture.setOnline(false)')
    page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(200)
    page.locator('#recordWeight').fill('90');page.locator('#recordReps').fill('3');page.locator('#recordAdd').click();page.wait_for_timeout(200)
    assert page.locator('#syncStatus').inner_text()=='서버 연결 후 자동으로 반영됩니다.'
    assert page.locator('#syncStatus').is_visible()
    page.wait_for_timeout(2400)
    assert page.locator('#syncStatus').is_visible()
    assert 0 < page.locator('#syncStatus').evaluate('(el)=>Number(getComputedStyle(el).opacity)') < 1
    page.wait_for_timeout(700)
    assert page.locator('#syncStatus').is_hidden()
    page.evaluate('appSync.retry()');page.wait_for_timeout(100)
    assert page.locator('#syncStatus').is_hidden()
    identity=page.evaluate('records.bench[0].firestoreId')
    assert identity and not identity.startswith('local_')
    assert page.evaluate("Object.keys(appSync.outbox.read('alice').ops).length")>0
    page.reload();page.wait_for_timeout(500)
    assert page.evaluate('(id)=>records.bench.filter(r=>r.firestoreId===id).length',identity)==1
    assert page.evaluate("Object.keys(appSync.outbox.read('alice').ops).length")==0
    assert page.locator('#syncStatus').inner_text()=='대기 중이던 기록을 서버에 반영했습니다.'
    assert page.locator('#syncStatus').evaluate('(el)=>getComputedStyle(el).whiteSpace')=='nowrap'
    assert page.locator('#syncStatus').is_visible()
    page.wait_for_timeout(3100)
    assert page.locator('#syncStatus').is_hidden()
    page.evaluate('(id)=>deleteRecord(id)',identity);page.wait_for_timeout(200)
    assert page.locator('#syncStatus').is_hidden()
    # Recovery during the same visit also reports completion once.
    context.set_offline(True)
    page.evaluate("fixture.setOnline(false); privateWrite('alice','records','toast-retry',{lift:'bench',weight:10,reps:1})")
    assert page.locator('#syncStatus').inner_text()=='서버 연결 후 자동으로 반영됩니다.'
    page.evaluate('fixture.setOnline(true)')
    context.set_offline(False)
    page.wait_for_timeout(200)
    assert page.locator('#syncStatus').inner_text()=='대기 중이던 기록을 서버에 반영했습니다.'
    page.wait_for_timeout(3100)
    page.evaluate('appSync.retry()');page.wait_for_timeout(100)
    assert page.locator('#syncStatus').is_hidden()
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
    # Summary integration uses existing guest records; no extra record copies are stored.
    first_session=page.evaluate('workoutSession.state().active.id')
    page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(700)
    page.locator('#tab2 .mf-warmup-toggle').check()
    page.locator('#recordWeight').fill('20');page.locator('#recordReps').fill('10');page.locator('#recordAdd').click();page.wait_for_timeout(200)
    page.locator('#tab2 .mf-warmup-toggle').uncheck()
    page.evaluate("myRoutineSaveAccessorySet('풀업','bodyweight',0,15)");page.wait_for_timeout(200)
    counts=page.evaluate('MFWorkout.summarize(workoutRows().filter(r=>r.sessionId===workoutSession.state().active.id))')
    assert counts['exercises']==2 and counts['sets']==2 and counts['warmupSets']==1 and counts['volume']==400,counts
    page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(700)
    page.on('dialog',lambda dialog:dialog.accept())
    page.locator('#workoutSummaryCard .mf-finish-workout').click();page.wait_for_timeout(1000)
    assert page.evaluate('workoutSession.state().active') is None
    last=page.evaluate('workoutSession.state().last')
    assert last['summary']['volume']==400 and last['summary']['sets']==2,last
    assert page.locator('#lastWorkoutSummary').inner_text().find('준비 1세트')>=0
    assert page.locator('#weeklyGrowthSummary').inner_text().find('한국 시간')>=0
    for light in [True,False]:
        page.evaluate('(v)=>applyLightMode(v)',light)
        page.locator('#workoutSummaryCard').scroll_into_view_if_needed()
        page.screenshot(path=f'/tmp/ttt-summary-{light}.png')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.reload();page.wait_for_timeout(300)
    assert page.evaluate('workoutSession.state().active') is None
    assert page.evaluate('workoutSession.state().last.summary.volume')==400
    page.locator('.bottomTab .tabBtn[data-target="tab2"]').click();page.wait_for_timeout(700)
    page.locator('#recordWeight').fill('85');page.locator('#recordReps').fill('5');page.locator('#recordAdd').click();page.wait_for_timeout(200)
    assert page.evaluate('workoutSession.state().active.id')!=first_session
    # A save during the old manual-stop animation must keep the new stopwatch running.
    page.evaluate('stopRestTimerManually(); setTimeout(resetRestTimerOnSave,50)');page.wait_for_timeout(1400)
    assert page.evaluate('restTimerActive')
    assert page.evaluate("JSON.parse(localStorage.getItem(appSync.account.key('mf_rest_stopwatch_v1'))).active")
    assert not errors,errors
    # Deletion UI is exercised only against this fixture. Popup cancellation is non-destructive.
    page.evaluate("localStorage.setItem('fixture_uid','delete-test');localStorage.setItem('mf_data_owner_v2','delete-test')")
    page.reload();page.wait_for_timeout(500)
    page.evaluate("fixture.store.set('users/delete-test/records/keep',{lift:'bench',weight:60,reps:5});fixture.setReauthError(true)")
    page.evaluate('deleteUserAccount()')
    assert page.evaluate("fixture.store.has('users/delete-test/records/keep')")
    assert page.evaluate("appSync.outbox.isDeleting('delete-test')") is False
    # A partial previous deletion must stay frozen even if its next reauthentication is canceled.
    page.evaluate("localStorage.setItem('mf_account_v2:delete-test:deleting','1')")
    page.evaluate('deleteUserAccount()')
    assert page.evaluate("appSync.outbox.isDeleting('delete-test')")
    page.evaluate('fixture.setReauthError(false); fixture.setDeleteError(true)')
    page.evaluate('deleteUserAccount()')
    assert not page.evaluate("fixture.store.has('users/delete-test/records/keep')")
    assert page.evaluate("appSync.outbox.isDeleting('delete-test')")
    # Retry cleanup after Auth deletion failure; other users/public docs remain.
    page.evaluate("fixture.store.set('users/other/records/keep',{reps:3});fixture.store.set('dexPosts/public',{name:'public'});fixture.setDeleteError(false)")
    page.evaluate('deleteUserAccount()');page.wait_for_timeout(500)
    assert page.evaluate("localStorage.getItem('mf_account_v2:delete-test:deleting')") is None
    assert page.evaluate('appSync.account.owner')=='guest'
    assert not errors,errors
    print('PASS: mobile sync/timer/summary workflows and isolated reauthentication cancellation, partial Auth deletion failure and retry')
    browser.close()
