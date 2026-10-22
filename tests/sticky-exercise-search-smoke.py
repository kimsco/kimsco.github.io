"""Sticky exercise search geometry and controls, with fake Firebase."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8198','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width,height in [(320,740),(390,844)]:
   c=b.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
   fixture=(root/'tests/firebase-fixture.js').read_text()
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();page.goto('http://127.0.0.1:8198/');page.wait_for_timeout(700)
   page.locator('.bottomTab .tabBtn[data-target="tab4"]').click();page.wait_for_timeout(500)
   page.evaluate("currentExercises=Array.from({length:40},(_,i)=>'테스트 종목 '+String(i).padStart(2,'0'));exerciseSearchQuery='';renderExercises()")
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light)
    page.evaluate('document.getElementById("exercise-screen").scrollTop=0');page.wait_for_timeout(350)
    search=page.locator('#exercise-screen > .search-wrap');before=search.bounding_box()
    assert not page.locator('#exercise-screen').evaluate("el=>el.classList.contains('search-scrolled')")
    page.evaluate('document.getElementById("exercise-screen").scrollTop=24');page.wait_for_timeout(100)
    midpoint=search.evaluate("el=>({bg:getComputedStyle(el,'::before').backgroundColor,blur:getComputedStyle(el,'::before').backdropFilter,mask:getComputedStyle(el,'::before').maskImage})")
    assert '0.75)' in midpoint['bg'] and midpoint['blur']=='blur(4px)' and 'gradient' in midpoint['mask'],midpoint
    page.evaluate('document.getElementById("exercise-screen").scrollTop=250');page.wait_for_timeout(350)
    after=search.bounding_box();assert abs(after['y']-before['y'])<.5,(before,after)
    assert after['x']>=0 and after['x']+after['width']<=width+.5
    styles=search.evaluate("el=>({opacity:getComputedStyle(el).opacity,bg:getComputedStyle(el,'::before').backgroundColor,blur:getComputedStyle(el,'::before').backdropFilter})")
    assert styles['opacity']=='1' and '0.5)' in styles['bg'] and styles['blur']=='blur(8px)',styles
    edge=search.evaluate("el=>{const s=getComputedStyle(el,'::before');const fade=parseFloat(getComputedStyle(el).getPropertyValue('--search-fade'));return parseFloat(s.top)+parseFloat(s.height)-fade+el.getBoundingClientRect().top-el.querySelector('.exercise-search-box').getBoundingClientRect().bottom;}")
    assert abs(edge)<.1,edge # Measure the actual input border, not the taller row created by button margins.

    page.screenshot(path='/tmp/sticky-search-'+str(width)+'-'+str(light)+'.png')
    # Real clicks still reach the fixed controls rather than cards behind them.
    page.locator('#exerciseSortBtn').click()
    page.locator('#exerciseSearchInput').fill('종목 12');page.wait_for_timeout(350)
    assert page.locator('#exercise-list .exercise-card').count()==1
    assert page.locator('#exercise-screen').evaluate('el=>el.scrollTop')==0
    assert not page.locator('#exercise-screen').evaluate("el=>el.classList.contains('search-scrolled')")
    page.locator('#exerciseSearchInput').fill('');page.wait_for_timeout(200)
    page.locator('#add-exercise-btn').click();assert page.locator('#addExerciseModal').is_visible()
    page.evaluate('closeAddExerciseModal()');page.wait_for_timeout(300)
   # A populated next part must still start at the top; test delayed loads and arm launchers.
   page.evaluate("window.originalLoadExercises=loadExercises;loadExercises=async part=>{await new Promise(r=>setTimeout(r,60));currentExercises=Array.from({length:40},(_,i)=>part+' '+i);renderExercises();}")
   for part in ['back','shoulder','arm_tri','chest']:
    page.evaluate('document.getElementById("exercise-screen").scrollTop=180');page.wait_for_timeout(80)
    if part=='arm_tri':page.locator('.folderBtn4[data-arm-launcher]').click()
    elif part=='chest':page.evaluate('document.querySelector(".folderBtn4[data-arm-back]").click()')
    else:page.locator('.folderBtn4[data-part="'+part+'"]').click()
    page.wait_for_timeout(250)
    assert page.evaluate('currentPart')==part
    assert page.locator('#exercise-screen').evaluate('el=>el.scrollTop')==0
    assert page.locator('#exercise-screen').evaluate("el=>el.style.getPropertyValue('--search-progress')")=='0'
   page.evaluate('loadExercises=originalLoadExercises')
   print('PASS sticky search',width,'both themes, fixed position, half-transparent backing, opaque controls, search/sort/add and reset at top')
   c.close()
  b.close()
finally:server.terminate();server.wait()
