"""Web startup layout checks; iOS native launch transitions require a real device."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
fixture=(ROOT/'tests/firebase-fixture.js').read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for light,reduced,width in [(False,False,320),(False,False,390),(True,False,390),(False,True,390)]:
  c=b.new_context(viewport={'width':width,'height':824},is_mobile=True,reduced_motion='reduce' if reduced else 'no-preference')
  c.add_init_script("Object.defineProperty(navigator,'standalone',{value:true});Object.defineProperty(screen,'height',{value:844});Object.defineProperty(screen,'width',{value:"+str(width)+"});localStorage.setItem('mf_light_mode','"+('1' if light else '0')+"');")
  # Hold readiness while measuring layout, independent of machine parsing speed.
  c.add_init_script("document.addEventListener('DOMContentLoaded',()=>{window.__startupUpdateReady=new Promise(resolve=>window.__releaseSplashLayoutCheck=()=>resolve(false));},{once:true});")
  def route(r):
   r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript')
  c.route('https://**/*',route)
  page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8000/',wait_until='domcontentloaded')
  assert page.evaluate("getComputedStyle(document.getElementById('bottomTab')).visibility")=='hidden'
  assert page.evaluate("getComputedStyle(document.getElementById('tab1')).visibility")=='hidden'
  a=page.locator('#bootSplash img').bounding_box()
  assert abs(a['y']+a['height']/2-422)<.1,a
  assert abs(a['x']+a['width']/2-width/2)<.1,a
  indicator=page.locator('#bootSplashLoading');dots=indicator.locator('.boot-splash-wave i');assert dots.count()==7;first=dots.first
  assert indicator.get_attribute('role')=='status' and indicator.get_attribute('aria-label')=='앱 불러오는 중'
  ring=indicator.bounding_box();assert abs(ring['x']+ring['width']/2-width/2)<.1
  assert abs(ring['y']-a['y']-a['height']-24)<.1 and ring['width']==64 and ring['height']==24
  names=dots.evaluate_all('(els)=>els.map(el=>getComputedStyle(el).animationName)')
  if reduced:assert names==['none']*7
  else:
   assert names==['boot-loading-wave']*7
   delays=dots.evaluate_all('(els)=>els.map(el=>parseFloat(getComputedStyle(el).animationDelay))')
   assert all(abs(delays[i]-i*.1)<.001 for i in range(7)),delays
   # Pause at the individual peak/rest times: centers must stay fixed as dots grow.
   shapes=dots.evaluate_all("""els=>els.map(el=>{const a=el.getAnimations()[0],time=a.currentTime;a.pause();a.currentTime=0;const start=el.getBoundingClientRect();a.currentTime=(parseFloat(getComputedStyle(el).animationDelay)+.28)*1000;const peak=el.getBoundingClientRect();a.currentTime=(parseFloat(getComputedStyle(el).animationDelay)+.56)*1000;const rest=el.getBoundingClientRect();a.currentTime=time;a.play();return {width:peak.width,peak:peak.height,rest:rest.height,centerShift:(peak.y+peak.height/2)-(start.y+start.height/2)};})""")
   for shape in shapes:assert shape['width']==4 and abs(shape['peak']-20)<.1 and abs(shape['rest']-4)<.1 and abs(shape['centerShift'])<.1,shape
  logo=page.locator('#bootSplash img')
  if reduced:assert logo.evaluate('(el)=>getComputedStyle(el).animationName')=='none'
  else:
   assert logo.evaluate('(el)=>getComputedStyle(el).animationName')=='boot-splash-appear'
   fade=logo.evaluate('(el)=>el.getAnimations()[0].effect.getKeyframes().map(k=>k.opacity)')
   assert fade==['0','1'],fade
   assert indicator.evaluate('(el)=>getComputedStyle(el).animationName')=='boot-splash-appear'
  if not light and not reduced and width==320:
   assets=page.evaluate("""async()=>{const results=[];for(const link of document.querySelectorAll('link[rel="apple-touch-startup-image"]')){const image=new Image();image.src=link.href;await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;let black=true;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2]||pixels[i+3]!==255){black=false;break;}results.push({path:new URL(link.href).pathname,width:image.naturalWidth,height:image.naturalHeight,black});}return results;}""")
   assert len(assets)==10
   for asset in assets:
    assert asset['black'] and '/icons/splash/black/' in asset['path'],asset
    assert asset['path'].endswith(str(asset['width'])+'x'+str(asset['height'])+'.png'),asset
  page.screenshot(path=f'/tmp/boot-loading-{width}-{light}-{reduced}.png')
  assert page.locator('meta[name="theme-color"]').get_attribute('content')=='#000000'
  page.set_viewport_size({'width':width,'height':844})
  z=page.locator('#bootSplash img').bounding_box()
  assert abs(a['y']-z['y'])<.1,(a,z)
  page.evaluate('window.__releaseSplashLayoutCheck()')
  page.wait_for_timeout(1200)
  assert page.locator('#bootSplash').count()==0
  assert page.evaluate("getComputedStyle(document.getElementById('tab1')).visibility")=='visible'
  assert page.evaluate("getComputedStyle(document.getElementById('bottomTab')).visibility")=='visible'
  assert page.locator('meta[name="theme-color"]').get_attribute('content')==('#ffffff' if light else '#000000')
  assert page.evaluate("getComputedStyle(document.body).backgroundColor")==('rgb(255, 255, 255)' if light else 'rgb(0, 0, 0)')
  assert not errors,errors
  page.goto('http://127.0.0.1:8000/?modeswitch=1',wait_until='domcontentloaded')
  assert not page.locator('#bootSplash').is_visible()
  assert not page.evaluate("document.documentElement.classList.contains('mf-boot-hold')")
  assert page.locator('meta[name="theme-color"]').get_attribute('content')==('#ffffff' if light else '#000000')
  c.close()
 b.close()
 print('PASS: centered startup logo and seven staggered dot-to-bar waves at 320/390px, dark/light handoff, reduced motion, viewport resize and mode-switch bypass')
