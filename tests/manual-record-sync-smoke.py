"""Manual-only history refresh, one original write, failure and account isolation."""
from pathlib import Path
import subprocess,sys,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text().replace("get:async(options)=>{calls.push({path,type:'query'", "get:async(options)=>{if(window.fixtureQueryGate && /\\/(records|accessoryRecords)$/.test(path))await window.fixtureQueryGate;calls.push({path,type:'query'")
server=subprocess.Popen([sys.executable,'-m','http.server','8196','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True)
  context.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
  context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8196/');page.wait_for_timeout(1200)
  assert not page.locator('#manualRecordSyncBtn').evaluate('(el)=>el.hidden')
  page.evaluate("appSync.write('alice','records','one',{lift:'bench',date:'20.01.01',weight:60,reps:5,createdAt:1})")
  page.wait_for_function("Object.keys(appSync.outbox.read('alice').ops).length===0")
  assert page.evaluate("fixture.calls.filter(x=>x.type==='set' && x.path==='users/alice/records/one').length")==1
  assert not page.evaluate("fixture.calls.some(x=>x.path.includes('recordUpdates'))")
  page.evaluate("reloadWorkoutRecords()")
  assert page.evaluate("records.bench[0].weight")==60
  page.evaluate("fixture.store.delete('users/alice/records/one');fixture.store.set('users/alice/accessoryRecords/two',{exercise:'Press',part:'chest',date:'20.01.01',weight:30,reps:8,createdAt:1})")
  # Normal focus never downloads changed history automatically.
  page.evaluate("refreshVisibleRecordData()");page.wait_for_timeout(100)
  assert page.evaluate("records.bench.length")==1
  page.evaluate("()=>{window.fixtureQueryGate=new Promise(r=>window.releaseQuery=r);window.firstManual=reloadWorkoutRecords();window.secondManual=reloadWorkoutRecords();}")
  assert page.evaluate('firstManual===secondManual')
  page.evaluate("releaseQuery();fixtureQueryGate=null;firstManual")
  assert page.evaluate("records.bench.length===0 && accRecordsByExercise.Press[0].weight===30")
  before=page.evaluate("JSON.stringify(accRecordsByExercise)")
  page.evaluate("fixture.setDenied(true)")
  assert page.evaluate("reloadWorkoutRecords().then(()=>false,()=>true)")
  assert page.evaluate("JSON.stringify(accRecordsByExercise)")==before
  page.evaluate("fixture.setDenied(false)")
  page.locator('#openSettingsBtn').click();page.wait_for_timeout(400)
  page.locator('#manualRecordSyncBtn').click();page.wait_for_function("document.getElementById('manualRecordSyncLabel').textContent==='기록을 불러왔어요'")
  assert not page.locator('#manualRecordSyncBtn').is_disabled()
  page.screenshot(path='/tmp/manual-record-sync.png')
  page.evaluate("window.fixtureQueryGate=new Promise(r=>window.releaseQuery=r);window.switchedManual=reloadWorkoutRecords().then(()=>false,()=>true);fixture.auth.currentUser={uid:'bob'};appSync.account.select('bob','bob@example.test');releaseQuery();fixtureQueryGate=null")
  assert page.evaluate('switchedManual')
  assert page.evaluate("localStorage.getItem('mf_account_v2:bob:mf_records_v1')") is None
  assert not errors,errors
  context.close()
  guest=browser.new_context();guest.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  page=guest.new_page();page.goto('http://127.0.0.1:8196/');page.wait_for_timeout(1200)
  assert page.locator('#manualRecordSyncBtn').evaluate('(el)=>el.hidden')
  assert page.evaluate("reloadWorkoutRecords().then(()=>false,()=>true)")
  guest.close();browser.close()
 print('PASS: one original record write, no change feed, explicit refresh only, single flight, errors, switched account and guest visibility')
finally:server.terminate();server.wait()
