"""One baseline, cached navigation, and two empty delta reads after restart."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text().replace('  window.fixture={',"""  store.set('users/alice/accessories/chest',{list:['Chest press']});store.set('users/alice/accessories/back',{list:['Back row']});
 for(let i=0;i<100;i++)store.set('users/alice/accessoryRecords/record-'+i,{exercise:'Chest press',part:'chest',date:'20.01.01',weight:60,reps:5,createdAt:1});
 window.fixture={""",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("accRecordsByExercise['Chest press']?.length===100 && !workoutSyncPending")
 count="fixture.calls.filter(x=>x.rest).length"
 assert page.evaluate(count)==2
 page.evaluate('workoutLastSyncAt=0') # Even outside the lifecycle debounce, tab clicks never poll records.
 for _ in range(10):
  page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.locator('.bottomTab .tabBtn[data-target="tab4"]').click()
  page.locator('.folderBtn4[data-part="back"]').click();page.locator('.folderBtn4[data-part="chest"]').click()
 assert page.evaluate(count)==2
 page.evaluate("fixture.changeRecord('accessoryRecords','record-0',{weight:70});fixture.changeRecord('accessoryRecords','record-1',{deleted:true})")
 page.evaluate('syncWorkoutRecords({force:true})')
 assert page.evaluate("accRecordsByExercise['Chest press'].length===99 && accRecordsByExercise['Chest press'].find(r=>r.id==='record-0').weight===70")
 assert page.evaluate("fixture.calls.filter(x=>x.rest).slice(-2).reduce((n,x)=>n+Math.max(1,x.returnedDocuments),0)")==3
 page.reload();page.wait_for_function("!workoutSyncPending && fixture.calls.filter(x=>x.rest).length===2")
 assert page.evaluate("accRecordsByExercise['Chest press'].length")==99
 assert page.evaluate("fixture.calls.filter(x=>x.rest).every(x=>x.returnedDocuments===0)")
 assert not errors,errors
 print('PASS: baseline once; 10 tab round trips add no record queries; two changes cost 3 reads; restart costs two empty reads without replaying 100 records')
 b.close()
