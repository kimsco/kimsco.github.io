"""Query/document-count budgets under repeated navigation, reload and remote changes."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
fixture=fixture.replace('  window.fixture={',"""  const t=new Date(),day=String(t.getFullYear()).slice(-2)+'.'+String(t.getMonth()+1).padStart(2,'0')+'.'+String(t.getDate()).padStart(2,'0');
  store.set('users/alice/accessories/chest',{list:['Chest press']});store.set('users/alice/accessories/back',{list:['Back row']});
  for(let i=0;i<100;i++)store.set('users/alice/accessoryRecords/record-'+i,{exercise:'Chest press',part:'chest',date:day,weight:60,reps:5,createdAt:Date.now()-10000});
  window.fixture={""",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("accRecordsByExercise['Chest press']?.length===100 && currentExercises.includes('Chest press')")
 queryCount="fixture.calls.filter(x=>x.path==='users/alice/accessoryRecords' && x.type==='query').length"
 partCount="fixture.calls.filter(x=>x.path==='users/alice/accessories/chest' && x.type==='get').length"
 assert page.evaluate(queryCount)==1
 for _ in range(10):
  page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.locator('.bottomTab .tabBtn[data-target="tab4"]').click()
  page.locator('.folderBtn4[data-part="back"]').click();page.locator('.folderBtn4[data-part="chest"]').click()
 page.wait_for_timeout(100)
 assert page.evaluate(queryCount)==1
 assert page.evaluate(partCount)==1
 # Local edits must be reused instead of the cache's old response value.
 page.evaluate("currentExercises.push('Local exercise');saveAccListToLocal('chest',currentExercises)")
 page.locator('.folderBtn4[data-part="back"]').click();page.locator('.folderBtn4[data-part="chest"]').click()
 assert 'Local exercise' in page.locator('#exercise-list').inner_text()
 # Even after the old TTL passes, records are not fetched again.
 page.evaluate("window.originalNow=Date.now;Date.now=()=>originalNow()+301000")
 page.evaluate("refreshVisibleRecordData()");page.wait_for_timeout(300)
 assert page.evaluate(queryCount)==1
 # A different device publishes a deletion without rereading its source collection.
 page.evaluate("""async()=>{
 await appSync.recordUpdates.commit('alice',{collection:'accessoryRecords',id:'record-0',data:null,merge:false,revision:'remote-delete'});
 await syncRecordUpdates({force:true});
 }""")
 assert page.evaluate("accRecordsByExercise['Chest press'].length")==99
 assert page.evaluate(queryCount)==1
 # Account-local rows and coverage survive more than a month and app restart.
 page.evaluate("Date.now=originalNow;localStorage.setItem(appSync.account.key('mf_full_sync_at_alice'),'1')")
 page.reload();page.wait_for_timeout(1000)
 page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(100)
 assert page.evaluate(queryCount)==0
 page.evaluate("loadAccessoryRecords()");assert page.evaluate(queryCount)==0
 assert not errors,errors
 print('PASS: 100-record startup query stays at one across 10 tab/part round trips (100 returned docs versus 1100 without navigation reuse); remote deletions arrive through change pages; expired initial sync and reload make zero repeat record queries')
 b.close()
