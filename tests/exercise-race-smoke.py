"""Hold startup/chest/back reads and navigate before responses; no production requests."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
fixture=fixture.replace("get:async(options)=>{calls.push({path,type:'get',source:options?.source});", "get:async(options)=>{calls.push({path,type:'get',source:options?.source});if(path==='users/alice/accessories/chest')await new Promise(r=>window.releaseChest=r);if(path==='users/alice/accessories/back')await new Promise(r=>window.releaseBack=r);",1)
fixture=fixture.replace("get:async(options)=>{calls.push({path,type:'query'", "get:async(options)=>{if(path==='users/alice/myRoutineTemplates')await new Promise(r=>window.releaseRoutine=r);calls.push({path,type:'query'",1)
fixture=fixture.replace('  window.fixture={',"  store.set('users/alice/accessories/chest',{list:['Chest press']});store.set('users/alice/accessories/back',{list:['Back row']});\n  window.fixture={",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("typeof releaseChest==='function' && typeof releaseBack==='function' && typeof releaseRoutine==='function'")
 page.locator('.bottomTab .tabBtn[data-target="tab4"]').click()
 assert '불러오는 중' in page.locator('#exercise-list').inner_text()
 page.locator('.folderBtn4[data-part="back"]').click()
 page.evaluate('releaseBack()');page.wait_for_function("currentExercises.includes('Back row')")
 assert 'Chest press' not in page.locator('#exercise-list').inner_text()
 page.evaluate('releaseRoutine();releaseChest()');page.wait_for_timeout(400)
 assert page.evaluate('currentPart')=='back'
 assert page.locator('.folderBtn4.active').get_attribute('data-part')=='back'
 assert 'Back row' in page.locator('#exercise-list').inner_text()
 assert 'Chest press' not in page.locator('#exercise-list').inner_text()
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/accessories/chest' && x.type==='get').length")==1
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/accessories/back' && x.type==='get').length")==1
 page.locator('.folderBtn4[data-part="chest"]').click();page.wait_for_function("currentExercises.includes('Chest press')")
 assert 'Chest press' in page.locator('#exercise-list').inner_text()
 assert page.evaluate('loadAccListFromLocal("back")')==['Back row']
 assert not errors,errors
 print('PASS: startup does not reset back to chest; late chest response never overwrites back; cache remains per-part; startup/prefetch share reads; missing cache displays loading')
 b.close()
