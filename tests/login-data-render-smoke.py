"""Derived views update before unrelated login loads finish; isolated Firebase only."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
fixture=fixture.replace('onAuthStateChanged:fn=>{listeners.push(fn);setTimeout(()=>fn(auth.currentUser),0);}', 'onAuthStateChanged:fn=>{listeners.push(fn);window.testAuthListener=fn;}')
needle="get:async(options)=>{calls.push({path,type:'query'"
assert needle in fixture
fixture=fixture.replace(needle,"get:async(options)=>{if(path==='users/alice/myRoutineTemplates')await new Promise(r=>{window.releaseRoutine=r;});calls.push({path,type:'query'",1)
fixture=fixture.replace('  window.fixture={',"  const t=new Date();const today=String(t.getFullYear()).slice(-2)+'.'+String(t.getMonth()+1).padStart(2,'0')+'.'+String(t.getDate()).padStart(2,'0');store.set('users/alice/profile/weight',{log:{[today]:73.5}});store.set('users/alice/meals/meal-test',{id:'meal-test',date:today,name:'Test meal',protein:10,carb:20,fat:5,count:1});store.set('users/alice/calendar/'+t.getFullYear()+'-'+(t.getMonth()+1)+'-'+t.getDate(),{muscles:['가슴'],confirmed:true});\n  window.fixture={",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(1200)
 page.wait_for_function("userWeight.log?.[formatTodayYYMMDD()]===73.5",timeout=3000)
 page.wait_for_function("typeof releaseRoutine==='function'")
 loaded=page.evaluate('userWeight.log[formatTodayYYMMDD()]')
 before=page.locator('#homeWeightInput').input_value()
 # Home updates while the unrelated routine request is still pending, without navigation.
 assert page.locator('#homeWeightInput').input_value()=='73.5'
 page.wait_for_timeout(100)
 count=page.evaluate('fixture.calls.length')
 page.evaluate('scheduleLoadedViews();scheduleLoadedViews();scheduleLoadedViews()')
 page.wait_for_timeout(100)
 assert page.evaluate('fixture.calls.length')==count
 after=page.locator('#homeWeightInput').input_value()
 print({'serverWeightAlreadyLoaded':loaded,'homeBeforeAnyNavigation':before,'homeAfterRefresh':after})
 assert loaded==73.5 and before=='73.5' and after=='73.5'
 assert page.locator('#homeTodayMuscle').inner_text()=='가슴'
 assert page.locator('#homeDietKcal').inner_text().startswith('165 ')
 page.evaluate('releaseRoutine()');page.wait_for_timeout(300)
 assert not errors,errors
 print('PASS: received weight updates home without tab switching while routine load is blocked; coalesced renders make zero reads; meal and calendar summaries update too')
 b.close()
