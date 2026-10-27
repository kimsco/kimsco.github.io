"""Real app save/delete hooks with isolated Firebase and a mocked reminder service."""
from pathlib import Path
import json,subprocess,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen(['python','-m','http.server','8204','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  context=browser.new_context(user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',viewport={'width':390,'height':844})
  fixture=(root/'tests/firebase-fixture.js').read_text()
  context.route('https://**/*',lambda r:r.fulfill(body=fixture+"fixture.store.set('users/alice/pushDevices/legacy',{token:'legacy',platform:'ios'});" if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
  requests=[]
  key='BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
  def reminder_route(route):
   request=route.request
   body=json.loads(request.post_data) if request.post_data else None
   requests.append({'path':request.url.split('reminders.test')[-1],'method':request.method,'body':body})
   route.fulfill(body=json.dumps({'schema':1,'publicKey':key,'ready':True} if request.url.endswith('/config') else {'ok':True}),content_type='application/json')
  context.route('https://reminders.test/**',reminder_route)
  context.route('**/js/push-config.js*',lambda r:r.fulfill(body="window.MF_PUSH_CONFIG={reminderApiUrl:'https://reminders.test'};",content_type='application/javascript'))
  context.add_init_script("""(()=>{
   localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');
   localStorage.setItem('mf_push_device_id_v1','legacy');localStorage.setItem('mf_push_binding_v1',JSON.stringify({uid:'alice',deviceId:'legacy',needsRotation:false}));
   Object.defineProperty(navigator,'standalone',{value:true});window.Notification={permission:'granted'};
   window.fixtureUnsubscribe=0;window.fixtureSubscribe=0;window.fixtureCurrentSub={unsubscribe:async()=>{fixtureUnsubscribe++;fixtureCurrentSub=null;return true;}};
   navigator.serviceWorker.getRegistration=async()=>({active:{postMessage:(message,ports)=>{if(ports?.[0])ports[0].postMessage({worker:'mf-v154',receipt:null});}},pushManager:{
    getSubscription:async()=>fixtureCurrentSub,subscribe:async(options)=>{fixtureSubscribe++;fixtureCurrentSub={options,unsubscribe:async()=>{fixtureUnsubscribe++;fixtureCurrentSub=null;return true;},toJSON:()=>({endpoint:'https://web.push.apple.com/fixture',keys:{p256dh:'fixture',auth:'fixture'}})};return fixtureCurrentSub;}
   }});
  })();""")
  page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  page.goto('http://127.0.0.1:8204/');page.wait_for_timeout(1200)
  assert not errors,errors
  assert any(r['path']=='/device' and r['method']=='PUT' for r in requests),requests
  assert page.evaluate('fixtureSubscribe')==1 and page.evaluate('fixtureUnsubscribe')==1
  assert page.evaluate("fixture.calls.some(c=>c.type==='delete'&&c.path==='users/alice/pushDevices/legacy')")
  assert not page.evaluate("fixture.calls.some(c=>c.type==='set'&&c.path.includes('/pushDevices/'))")
  page.wait_for_function("localStorage.getItem('mf_account_v2:alice:reminder_activity_v1')!==null")
  assert [r['body']['hasRecord'] for r in requests if r['path']=='/activity']==[False]
  page.evaluate("()=>{recordWeight.value='50';recordReps.value='5';recordAdd.click();}")
  page.wait_for_function("JSON.parse(localStorage.getItem('mf_account_v2:alice:reminder_activity_v1')).hasRecord===true")
  assert [r['body']['hasRecord'] for r in requests if r['path']=='/activity']==[False,True]
  reads=page.evaluate("fixture.calls.filter(c=>c.rest).length")
  page.evaluate("()=>{recordWeight.value='55';recordReps.value='5';recordAdd.click();}");page.wait_for_timeout(500)
  assert page.evaluate("fixture.calls.filter(c=>c.rest).length")==reads
  assert [r['body']['hasRecord'] for r in requests if r['path']=='/activity']==[False,True]
  page.evaluate("async()=>{const ids=Object.values(records).flat().map(r=>r.firestoreId).filter(Boolean);for(const id of ids)await deleteRecord(id);}")
  page.wait_for_function("JSON.parse(localStorage.getItem('mf_account_v2:alice:reminder_activity_v1')).hasRecord===false")
  assert [r['body']['hasRecord'] for r in requests if r['path']=='/activity']==[False,True,False]
  for r in requests:
   if r['path']=='/activity':assert sorted(r['body'])==['basis','day','deviceId','hasLocalRecord','hasRecord']
  page.evaluate("()=>{handleAuthSession=async()=>{};document.getElementById('logoutConfirm').click();}")
  page.wait_for_function('fixture.auth.currentUser===null')
  assert any(r['path']=='/device' and r['method']=='DELETE' for r in requests)
  assert not errors,errors
  print('PASS legacy migration, minimal activity, first-set/last-delete transitions, unchanged-state dedupe, logout cleanup')
  browser.close()
finally:server.terminate();server.wait()
