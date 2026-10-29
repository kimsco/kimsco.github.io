"""Title resolution, persistence, editing, safe rendering and stale-result guards."""
import subprocess,time,json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8214','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   context=browser.new_context(viewport={'width':width,'height':844});calls=[]
   def route(r):
    url=r.request.url
    if 'microlink.io' in url:
     calls.append(url)
     r.fulfill(json={'status':'success','data':{'title':'페이지 "제목" <img src=x onerror=alert(1)>'}})
    elif '/oembed?' in url:
     calls.append(url);r.fulfill(json={'title':'체스트 프레스 자세 배우기'})
    else:r.fulfill(body=fixture if '/firebase-app-compat.js' in url else '',content_type='application/javascript')
   context.route('https://**/*',route)
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8214');page.wait_for_timeout(1300)
   page.evaluate("exerciseRefLinks={};addExerciseRefLink('가슴','https://youtu.be/abc');addExerciseRefLink('가슴','https://example.com/guide');openExerciseRefModal('가슴')")
   page.wait_for_function("getExerciseRefLinks('가슴').every(item=>item.title)")
   links=page.locator('.exercise-ref-row-link');assert links.nth(0).inner_text()=='체스트 프레스 자세 배우기';assert '<img' in links.nth(1).inner_text()
   assert page.locator('#exerciseRefList img').count()==0;assert links.nth(1).get_attribute('title')=='https://example.com/guide'
   page.evaluate('renderExerciseRefList()');assert links.nth(1).get_attribute('href')=='https://example.com/guide'
   assert page.locator('#exerciseRefModal').evaluate('e=>e.scrollWidth<=innerWidth')
   # Existing pencil action edits URL then title, and manual titles survive reopening.
   answers=iter(['https://youtu.be/abc','내 운동 참고영상']);page.on('dialog',lambda d:d.accept(next(answers)))
   page.locator('.exercise-ref-edit-btn').nth(0).click();assert links.nth(0).inner_text()=='내 운동 참고영상'
   count=len(calls);page.reload();page.wait_for_timeout(1300);page.evaluate("openExerciseRefModal('가슴')");page.wait_for_timeout(400)
   assert links.nth(0).inner_text()=='내 운동 참고영상';assert len(calls)==count
   # Failed metadata: original URL and no repeated lookups while reopening.
   context.route('https://api.microlink.io/**',lambda r:r.fulfill(status=429,json={'status':'fail'}))
   page.evaluate("addExerciseRefLink('가슴','https://instagram.com/reel/abc');renderExerciseRefList()")
   page.wait_for_function("getExerciseRefLinks('가슴')[2].titleCheckedAt>0")
   assert links.nth(2).inner_text()=='https://instagram.com/reel/abc'
   # A delayed result cannot overwrite a manual edit or restore a deleted item.
   page.evaluate("""()=>{window.finishTitle=null;MFLinkTitles.getTitle=()=>new Promise(r=>finishTitle=r);addExerciseRefLink('지연','https://example.com/late');const item=getExerciseRefLinks('지연')[0];updateExerciseRefLink('지연',item.id,item.url,'직접 지정');finishTitle('늦은 제목')}""")
   page.wait_for_timeout(50);assert page.evaluate("getExerciseRefLinks('지연')[0].title")=='직접 지정'
   page.evaluate("""()=>{addExerciseRefLink('삭제','https://example.com/deleted');deleteExerciseRefLink('삭제',getExerciseRefLinks('삭제')[0].id);finishTitle('삭제된 제목')}""")
   page.wait_for_timeout(50);assert page.evaluate("getExerciseRefLinks('삭제').length")==0
   assert not errors,errors
   page.screenshot(path=f'/tmp/link-titles-{width}.png');print('PASS metadata titles, escaping, edit, persisted cache, fallback and stale results',width)
   context.close()
  browser.close()
finally:server.terminate();server.wait()
