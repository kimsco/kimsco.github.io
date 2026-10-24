"""Exercise list pending/empty/error states; isolated fake Firebase only."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8199','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844})
   fixture=(root/'tests/firebase-fixture.js').read_text()
   context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=context.new_page();page.goto('http://127.0.0.1:8199/');page.wait_for_timeout(700)
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(200)
   page.evaluate("""()=>{
    fixture.auth.currentUser={uid:'loading-test'};appSync.account.select('loading-test');
    currentPart='chest';exerciseSearchQuery='';
    readExerciseList=()=>new Promise((resolve,reject)=>{window.resolveList=resolve;window.rejectList=reject;});
    lsSet(LS_KEYS.accessoriesList('chest'),[]);window.listTask=loadExercises('chest');
   }""")
   spinner=page.locator('#exercise-list .exercise-list-loading')
   assert spinner.is_visible() and page.locator('#exercise-list').get_attribute('aria-busy')=='true'
   page.evaluate("resolveList(['벤치프레스'])");page.evaluate('listTask')
   assert not spinner.count() and page.locator('#exercise-list .exercise-card').count()==1
   assert page.locator('#exercise-list').get_attribute('aria-busy')=='false'
   # A completed empty result must stop spinning, rather than pretend to load forever.
   page.evaluate("window.listTask=loadExercises('chest');void 0")
   assert spinner.is_visible()
   page.evaluate('resolveList([])');page.evaluate('listTask')
   assert not spinner.count() and '아직 추가된 종목이 없습니다' in page.locator('#exercise-list').inner_text()
   page.evaluate("window.listTask=loadExercises('chest');void 0")
   assert spinner.is_visible()
   page.evaluate("rejectList(Error('fixture unavailable'))");page.evaluate('listTask')
   assert not spinner.count() and '불러오지 못했습니다' in page.locator('#exercise-list').inner_text()
   assert page.locator('#exercise-list').get_attribute('aria-busy')=='false'
   # Existing local cards remain visible while a refresh is pending.
   page.evaluate("lsSet(LS_KEYS.accessoriesList('chest'),['로컬 종목']);window.listTask=loadExercises('chest');void 0")
   assert not spinner.count() and '로컬 종목' in page.locator('#exercise-list').inner_text()
   page.evaluate("resolveList(['최신 종목'])");page.evaluate('listTask')
   assert '최신 종목' in page.locator('#exercise-list').inner_text()
   print('PASS: list pending spinner, loaded cards, confirmed empty, error, populated cache',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
