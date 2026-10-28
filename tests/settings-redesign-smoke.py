"""Settings presentation and existing navigation, with isolated Firebase only."""
from pathlib import Path
import subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8212','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  fixture=(root/'tests/firebase-fixture.js').read_text()
  for width in [320,390]:
   for signed_in in [False,True]:
    context=browser.new_context(viewport={'width':width,'height':844},is_mobile=True,has_touch=True)
    context.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
    if signed_in:context.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');")
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8212/');page.wait_for_timeout(850)
    page.evaluate('document.getElementById("openSettingsBtn").click()');page.wait_for_timeout(350)
    overlay=page.locator('#settingsOverlay');body=overlay.locator('.settings-body')
    assert overlay.locator('h1').inner_text()=='설정'
    assert page.locator('#settingsAccountSection').is_visible()==signed_in
    assert page.locator('#settingsLoginRow').is_visible()!=signed_in
    assert page.locator('#settingsGuestBadge').is_visible()==signed_in
    assert page.locator('#mySpecMenuBtn').is_visible()
    for light in [False,True]:
     page.evaluate('(value)=>applyLightMode(value)',light);body.evaluate('el=>el.scrollTop=0');page.wait_for_timeout(150)
     assert body.evaluate('el=>el.scrollWidth<=el.clientWidth')
     heights=overlay.locator('.settings-item').evaluate_all('els=>els.map(el=>el.getBoundingClientRect().height)')
     assert all(height==72 for height in heights),heights
     colors=overlay.locator('.settings-card').evaluate_all('els=>els.map(el=>getComputedStyle(el).backgroundColor)')
     assert all(color==('rgb(255, 255, 255)' if light else 'rgb(24, 24, 24)') for color in colors),colors
     assert 'radial-gradient' in page.locator('#settingsPanel').evaluate('el=>getComputedStyle(el).backgroundImage')
     assert page.locator('#homeSettingsMenuBtn .settings-chevron').count()==1
     assert page.locator('#unitSettingsMenuBtn .settings-chevron').count()==1
     assert page.locator('#installGuideMenuBtn .settings-chevron').count()==1
     assert page.locator('#notificationPermissionBox .settings-chevron').count()==0
     assert overlay.locator('.settings-item-icon').evaluate_all('els=>els.every(el=>getComputedStyle(el).width==="22px"||!!el.closest(".settings-profile-avatar"))')
     if signed_in:
      assert page.locator('#settingsLogoutText').evaluate('el=>getComputedStyle(el).color')!=page.locator('#settingsDeleteAccountText').evaluate('el=>getComputedStyle(el).color')
      assert page.locator('#settingsLogoutText').evaluate('el=>el.tagName')=='BUTTON'
     page.screenshot(path=f'/tmp/settings-redesign-{width}-{signed_in}-{light}.png')
    # All existing screen links still open and return normally.
    for button_id,screen,close in [('homeSettingsMenuBtn','homeSettingsOverlay','closeHomeSettings'),('unitSettingsMenuBtn','unitSettingsOverlay','closeUnitSettings'),('installGuideMenuBtn','installGuideOverlay','closeInstallGuide'),('mySpecMenuBtn','mySpecOverlay','closeMySpec')]:
     page.evaluate('if(settingsOverlay.classList.contains("hidden"))openSettingsBtn.click()');page.wait_for_timeout(300)
     page.locator('#'+button_id).click();page.wait_for_timeout(300);assert page.locator('#'+screen).is_visible(),screen
     page.evaluate(close+'()');page.wait_for_timeout(300)
    page.evaluate('if(settingsOverlay.classList.contains("hidden"))openSettingsBtn.click()');page.wait_for_timeout(300)
    page.locator('#notificationPermissionBox').click();assert page.locator('#notificationSettingsOverlay').is_visible()
    page.locator('#notificationSettingsBack').click()
    if signed_in:
     page.locator('#settingsLogoutText').click();assert page.locator('#logoutModal').is_visible();page.locator('#logoutCancel').click()
     page.locator('#settingsDeleteAccountText').click();assert page.locator('#deleteAccountModal').is_visible();page.locator('#deleteAccountCancel').click()
     assert not page.evaluate("fixture.calls.some(call=>call.type==='delete')")
    else:
     page.locator('#settingsLoginRow').click();assert page.locator('#loginSheet').is_visible()
    assert not errors,errors
    print('PASS settings redesign: layout, themes, identity and existing actions',width,signed_in)
    context.close()
  browser.close()
finally:server.terminate();server.wait()
