"""No resting header compositing/filter path; keep drawer motion and crisp layout."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8235','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);fixture=(root/'tests/firebase-fixture.js').read_text()
  for width,dpr in [(320,2),(393,3),(430,3)]:
   c=b.new_context(viewport={'width':width,'height':852},device_scale_factor=dpr,is_mobile=True,has_touch=True)
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8235');page.wait_for_timeout(1800)
   def check():
    state=page.evaluate('''()=>{const h=document.querySelector('.topBar'),s=getComputedStyle(h),before=getComputedStyle(h,'::before'),title=document.getElementById('topTitleText'),ts=getComputedStyle(title);return {transform:s.transform,filter:s.filter,backdrop:s.backdropFilter,before:before.backdropFilter,will:s.willChange,left:h.getBoundingClientRect().left,titleTransform:ts.transform,titleTranslate:ts.translate,icons:['navDrawerMenuIcon','openAnnouncementBtn','openSettingsBtn'].map(id=>getComputedStyle(document.getElementById(id)).filter)};}''')
    assert state['transform']==state['filter']==state['backdrop']==state['before']=='none',state
    assert state['titleTransform']==state['titleTranslate']=='none' and state['will']=='auto',state
    assert abs(state['left']*dpr-round(state['left']*dpr))<.06,state
    assert state['icons']==['none']*3,state
   for light in [False,True]:
    page.evaluate('v=>applyLightMode(v)',light)
    for tab in ['tab1','tab2','tab4','tab3']:
     page.locator('.bottomTab .tabBtn[data-target="'+tab+'"]').click();page.wait_for_timeout(100);check()
    page.locator('.bottomTab .tabBtn[data-target="tab1"]').click();page.wait_for_timeout(150)
    page.locator('#openNavDrawerBtn').click();page.wait_for_timeout(400)
    assert page.locator('.topBar').evaluate('e=>Math.abs(new DOMMatrixReadOnly(getComputedStyle(e).transform).m41-16)<.1')
    page.evaluate('closeNavDrawer()');page.wait_for_timeout(420);check()
    page.locator('#openSettingsBtn').click();page.wait_for_timeout(350)
    assert page.locator('.topBar').evaluate('e=>Math.abs(new DOMMatrixReadOnly(getComputedStyle(e).transform).m41+16)<.1')
    page.evaluate('closeSettings()');page.wait_for_timeout(350);check()
   assert not errors,errors
   print('PASS resting header filters/transforms, physical alignment, four tabs, themes and mirrored drawers',width,dpr);c.close()
  b.close()
finally:server.terminate();server.wait()
