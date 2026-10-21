"""Isolated full-history cache restart, expiry, remote edits and failed persistence."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text().replace('  window.fixture={',"""  store.set('users/alice/records/old-lift',{lift:'bench',date:'20.01.01',weight:60,reps:5,createdAt:1});
  store.set('users/alice/accessoryRecords/old-acc',{exercise:'Old press',part:'chest',date:'20.01.01',weight:30,reps:8,createdAt:1});
  window.fixture={""",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context()
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(1000)
 page.evaluate("Promise.all([ensureFullLiftHistory('bench'),ensureExerciseHistory('Old press')])")
 assert page.evaluate("records.bench.some(x=>x.firestoreId==='old-lift') && accRecordsByExercise['Old press'].some(x=>x.id==='old-acc')")
 page.reload();page.wait_for_timeout(800)
 count="fixture.calls.filter(x=>x.type==='query' && x.filters?.some(f=>f[1]==='==')).length"
 # Fixture calls do not expose filters: compare the before/after query count instead.
 count="fixture.calls.filter(x=>x.type==='query' && ['users/alice/records','users/alice/accessoryRecords'].includes(x.path)).length"
 before=page.evaluate(count)
 page.evaluate("Promise.all([ensureFullLiftHistory('bench'),ensureExerciseHistory('Old press')])")
 assert page.evaluate(count)==before
 # Time passing never causes a repeat query for already loaded history.
 before=page.evaluate(count)
 page.evaluate("window.originalNow=Date.now;Date.now=()=>originalNow()+86401000")
 page.evaluate("Promise.all([ensureFullLiftHistory('bench'),ensureExerciseHistory('Old press')])")
 assert page.evaluate(count)==before
 # Timestamped remote changes, including deletion, update only those rows.
 page.evaluate("fixture.changeRecord('records','old-lift',{deleted:true});fixture.changeRecord('accessoryRecords','old-acc',{weight:40});syncWorkoutRecords({force:true})")
 assert page.evaluate("!records.bench.some(x=>x.firestoreId==='old-lift') && accRecordsByExercise['Old press'][0].weight===40")
 # Bulk rename and delete write server timestamps without erasing data or looping on tombstones.
 page.evaluate("""async()=>{
 await appSync.write('alice','accessoryRecords','rename-old',{exercise:'Renamed press'},{matchExercise:'Old press'});
 while(Object.keys(appSync.outbox.read('alice').ops).length)await new Promise(r=>setTimeout(r,10));
 await syncWorkoutRecords({force:true});
 }""")
 assert page.evaluate("fixture.store.get('users/alice/accessoryRecords/old-acc').weight===40 && fixture.store.get('users/alice/accessoryRecords/old-acc').reps===8")
 assert page.evaluate("accRecordsByExercise['Renamed press'][0].weight===40")
 page.evaluate("""async()=>{
 await appSync.write('alice','accessoryRecords','delete-exercise',null,{matchExercise:'Renamed press'});
 while(Object.keys(appSync.outbox.read('alice').ops).length)await new Promise(r=>setTimeout(r,10));
 await syncWorkoutRecords({force:true});
 }""")
 assert page.evaluate("accRecordsByExercise['Renamed press'].length===0 && fixture.store.get('users/alice/accessoryRecords/old-acc').deleted===true")
 # Existing in-memory data must not be mistaken for successful durable storage.
 page.evaluate("()=>{window.originalSave=saveAccRecordsToLocal;saveAccRecordsToLocal=()=>{throw Error('quota');};}")
 page.evaluate("ensureExerciseHistory('Failure exercise')")
 assert page.evaluate("!exerciseHistoryFullyLoaded.has('Failure exercise')")
 assert page.evaluate("localStorage.getItem('mf_account_v2:alice:read_fresh:exerciseHistory:Failure exercise')===null")
 page.evaluate("saveAccRecordsToLocal=originalSave;ensureExerciseHistory('Failure exercise')")
 assert page.evaluate("exerciseHistoryFullyLoaded.has('Failure exercise')")
 page.evaluate("localStorage.removeItem(appSync.account.key(LS_KEYS.accessoryRecords))")
 before=page.evaluate(count);page.evaluate("ensureExerciseHistory('Old press')");assert page.evaluate(count)>before
 print('PASS: full-history cache survives restart; age does not reread history; delta sync receives edits/deletes; quota failure remains retryable; missing local cache forces reread')
 b.close()
