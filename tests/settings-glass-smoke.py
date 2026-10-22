"""Settings-only glass feedback and unchanged setting actions, with fake Firebase."""
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
   page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(400)
   assert page.locator('.settings-glass-toggle').count()==7
   assert not page.locator('#calendarToggle').evaluate("el=>el.classList.contains('settings-glass-toggle')")
   for light in [False,True]:
    page.evaluate('(v)=>applyLightMode(v)',light)
    toggle=page.locator('#restTimerToggle');toggle.scroll_into_view_if_needed();page.wait_for_timeout(400)
    before=toggle.evaluate("el=>({active:el.classList.contains('active'),rect:el.closest('.settings-item').getBoundingClientRect().toJSON()})")
    assert toggle.evaluate("el=>getComputedStyle(el.closest('.settings-item')).overflow")=='visible'
    dimensions=toggle.evaluate("el=>{const s=getComputedStyle(el,'::after');return [el.offsetWidth,el.offsetHeight,s.width,s.height,s.left,s.top]}")
    assert dimensions==[64,28,'36px','24px','2px','2px'],dimensions
    r=toggle.bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down();page.wait_for_timeout(150)
    assert toggle.evaluate("el=>el.classList.contains('glass-pressed')")
    assert toggle.evaluate("el=>el.closest('.settings-item').getBoundingClientRect().toJSON()")==before['rect']
    page.screenshot(path='/tmp/settings-glass-'+str(width)+'-'+str(light)+'-pressed.png')
    page.mouse.up();page.wait_for_timeout(750)
    assert toggle.evaluate("el=>el.classList.contains('active')")!=before['active']
    assert not toggle.evaluate("el=>el.classList.contains('glass-pressed')||el.classList.contains('glass-settling')")
    assert toggle.get_attribute('aria-checked')==str(not before['active']).lower()
    assert toggle.evaluate("el=>el.closest('.settings-item').getBoundingClientRect().toJSON()")==before['rect']
    for i in range(6):toggle.evaluate('el=>el.click()')
    page.wait_for_timeout(750)
    assert toggle.evaluate("el=>el.classList.contains('active')")!=before['active']
    toggle.focus();page.keyboard.press('Space');page.wait_for_timeout(750)
    assert toggle.evaluate("el=>el.classList.contains('active')")==before['active']
    page.emulate_media(reduced_motion='reduce');toggle.evaluate('el=>el.click()');page.wait_for_timeout(50)
    assert toggle.evaluate("el=>getComputedStyle(el,'::after').transitionDuration")=='0s'
    page.emulate_media(reduced_motion='no-preference');page.wait_for_timeout(700)
    page.screenshot(path='/tmp/settings-glass-'+str(width)+'-'+str(light)+'.png')
   # One continuous click motion: movement overlaps expansion; contraction starts only after arrival.
   trace=page.evaluate("""async()=>{const el=document.getElementById('restTimerToggle');if(el.classList.contains('active')){el.click();await new Promise(r=>setTimeout(r,500));}el.click();const frames=[];for(let i=0;i<32;i++){await new Promise(requestAnimationFrame);const m=new DOMMatrixReadOnly(getComputedStyle(el,'::after').transform);frames.push([m.m41,m.m11,m.m22]);}return frames;}""")
   assert any(2<x<18 and sx>1.15 for x,sx,sy in trace),trace
   assert any(20<x<23.99 and sx>1.5 for x,sx,sy in trace),trace
   assert any(abs(x-24)<.01 and 1.02<sx<1.55 for x,sx,sy in trace),trace
   moving=[sx for x,sx,sy in trace if x<23.99]
   assert all(b>=a-.005 for a,b in zip(moving,moving[1:])),trace
   assert abs(trace[-1][0]-24)<.1 and abs(trace[-1][1]-1)<.01,trace
   # Horizontal drag previews position, commits once, and never toggles on cancellation.
   page.evaluate("()=>{const el=document.getElementById('restTimerToggle');if(el.classList.contains('active'))el.click();window.dragSettingClicks=0;el.addEventListener('click',()=>window.dragSettingClicks++);}")
   page.wait_for_timeout(700)
   toggle=page.locator('#restTimerToggle');toggle.scroll_into_view_if_needed()
   r=toggle.bounding_box();x=r['x']+20;y=r['y']+14
   page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+9,y,steps=3)
   assert toggle.evaluate("el=>el.style.getPropertyValue('--glass-x')")=='9px'
   assert not toggle.evaluate("el=>el.classList.contains('active')")
   page.mouse.move(x+24,y,steps=4);page.mouse.up();page.wait_for_timeout(750)
   assert toggle.get_attribute('aria-checked')=='true'
   assert page.evaluate('dragSettingClicks')==1
   # Drag back within the ON half: no write and no compatibility click toggle.
   page.mouse.move(x+24,y);page.mouse.down();page.mouse.move(x+18,y,steps=3);page.mouse.up();page.wait_for_timeout(750)
   assert toggle.get_attribute('aria-checked')=='true' and page.evaluate('dragSettingClicks')==1
   # Capture follows the pointer even outside the switch.
   page.mouse.move(x+24,y);page.mouse.down();page.mouse.move(x-50,y,steps=5);page.mouse.up();page.wait_for_timeout(750)
   assert toggle.get_attribute('aria-checked')=='false' and page.evaluate('dragSettingClicks')==2
   page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y,steps=3)
   toggle.dispatch_event('pointercancel');page.mouse.move(0,0);page.mouse.up();page.wait_for_timeout(750)
   assert toggle.get_attribute('aria-checked')=='false' and page.evaluate('dragSettingClicks')==2
   assert not toggle.evaluate("el=>el.classList.contains('glass-dragging')||el.classList.contains('glass-pressed')")
   # Real touchscreen events through Chromium's input pipeline.
   cdp=c.new_cdp_session(page)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
   for offset in [6,12,18,24]:
    cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+offset,'y':y}]});page.wait_for_timeout(30)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(750)
   assert toggle.get_attribute('aria-checked')=='true' and page.evaluate('dragSettingClicks')==3
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
   for offset in [10,25,45]:
    cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y-offset}]});page.wait_for_timeout(30)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(750)
   assert toggle.get_attribute('aria-checked')=='true' and page.evaluate('dragSettingClicks')==3
   print('PASS settings glass',width,'press/release, layout stability, rapid clicks, keyboard, aria, reduced motion and both themes')
   c.close()
  b.close()
finally:server.terminate();server.wait()
