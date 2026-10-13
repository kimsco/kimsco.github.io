"""Isolated chronological server pagination with same-date boundary records."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text().replace('  window.fixture={',"""  for(let i=0;i<123;i++){
 const id='old-'+String(i).padStart(3,'0');
 store.set('users/alice/records/'+id,{lift:'bench',date:'20.01.01',weight:60,reps:5,createdAt:1});
 store.set('users/alice/accessoryRecords/'+id,{exercise:'Old press',part:'chest',date:'20.01.01',weight:30,reps:8,createdAt:1});
 } window.fixture={""",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context()
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(1000)
 page.evaluate("historyPages.next('accessory','Old press',getRecordsInitialWindowStartDateStr())")
 assert page.evaluate("accRecordsByExercise['Old press'].length")==50
 page.reload();page.wait_for_timeout(700)
 page.evaluate("historyPages.next('accessory','Old press',getRecordsInitialWindowStartDateStr())")
 assert page.evaluate("accRecordsByExercise['Old press'].length")==100
 page.evaluate("historyPages.next('accessory','Old press',getRecordsInitialWindowStartDateStr())")
 assert page.evaluate("accRecordsByExercise['Old press'].length")==123
 assert page.evaluate("new Set(accRecordsByExercise['Old press'].map(x=>x.id)).size")==123
 assert page.evaluate("historyPages.done('accessory','Old press')")
 calls=page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/accessoryRecords' && x.filters?.some(f=>f[0]==='exercise'))")
 assert len(calls)==2 and all(x['maximum']==50 for x in calls)
 page.evaluate("historyPages.next('lift','bench',getRecordsInitialWindowStartDateStr())")
 assert page.evaluate("records.bench.length")==50
 assert not page.evaluate("liftFullHistoryLoaded.bench")
 # Failed page/index request surfaces a retry control and does not loop.
 page.evaluate("()=>{fixture.setDenied(true);const el=document.createElement('div');el.style.cssText='position:fixed;inset:0;overflow:auto;z-index:999999;background:black';document.body.appendChild(el);setupRecordInfiniteScroll(el,0,0,true,()=>{},()=>historyPages.next('accessory','Denied exercise',getRecordsInitialWindowStartDateStr()));}")
 page.wait_for_function("document.querySelector('.record-scroll-sentinel button')")
 before=page.evaluate("fixture.calls.length");page.wait_for_timeout(350)
 assert page.evaluate("fixture.calls.length")==before
 assert '다시 시도' in page.locator('.record-scroll-sentinel button').inner_text()
 assert not errors,errors
 print('PASS: server pages are capped at 50; 123 same-date records load in 3 pages without duplication; cursor survives app restart; lift list does not call full-history loader')
 b.close()
