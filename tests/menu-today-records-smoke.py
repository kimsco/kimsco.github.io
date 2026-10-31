"""Daily control-center card: full data, aggregation, dates, updates and safe text."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8229','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390,430]:
   context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8229');page.wait_for_timeout(1600)
   page.evaluate('''()=>{
    Object.keys(records).forEach(k=>records[k]=[]);accRecordsByExercise={};bodyweightRoutineRecords=[];
    applyMenuV2(true);openNavDrawer();
   }''');page.wait_for_timeout(400)
   assert page.locator('#navTodayRecordsEmpty').is_visible()
   page.evaluate('''()=>{
    const date=formatTodayYYMMDD();
    records.bench=[{date,weight:60,reps:10,sets:1,createdAt:100},{date,weight:'60',reps:'10',sets:2,createdAt:101},{date,weight:65,reps:8,sets:1,createdAt:102},{date:'00.01.01',weight:999,reps:1,sets:1}];
    accRecordsByExercise['랫풀다운']=[{exercise:'랫풀다운',date,weight:45,reps:12,createdAt:200},{exercise:'랫풀다운',date,weight:45,reps:12,createdAt:201}];
    for(let i=0;i<18;i++)accRecordsByExercise['운동 '+i]=[{exercise:'운동 '+i,date,weight:20+i,reps:15,createdAt:300+i}];
    accRecordsByExercise['안전한 이름']=[{exercise:'<img src=x onerror=alert(1)>',date,weight:0,reps:12,createdAt:400}];
    bodyweightRoutineRecords=[{date,routineName:'맨몸 루틴',totalReps:30,totalSets:3,completedAt:500}];
    window.dispatchEvent(new Event('mf-reminder-records-changed'));
   }''')
   rows=page.locator('#navTodayRecordsList li');assert rows.count()==22,rows.count()
   text=rows.first.inner_text();assert '60kg · 10회 × 3set' in text and '65kg · 8회 × 1set' in text,text
   assert '999' not in page.locator('#navTodayRecordsList').inner_text()
   assert '45kg · 12회 × 2set' in rows.nth(1).inner_text()
   assert page.locator('#navTodayRecordsList img').count()==0
   assert '총 3set · 30회' in rows.last.inner_text()
   assert page.locator('#navTodayRecordsEmpty').is_hidden()
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    assert page.locator('#navDrawer').bounding_box()['width']==width
    assert page.locator('.nav-today-card').evaluate('e=>e.scrollWidth<=e.clientWidth')
    body=page.locator('#navMenuBody');body.evaluate('e=>e.scrollTop=e.scrollHeight')
    assert body.evaluate('e=>e.scrollTop>0')
    assert rows.last.is_visible()
    page.screenshot(path=f'/tmp/menu-today-{width}-{light}.png')
   page.evaluate('''()=>{records.bench=[];accRecordsByExercise={};bodyweightRoutineRecords=[];window.dispatchEvent(new Event('mf-reminder-snapshot'));}''')
   assert rows.count()==0 and page.locator('#navTodayRecordsEmpty').is_visible()
   page.evaluate('applyMenuV2(false)');assert page.locator('#navTodayRecords').is_hidden()
   assert not errors,errors
   print('PASS all daily rows, grouped sets, updates, old dates, safe text, themes and scrolling',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
