"""Home date-summary migration/read-count/offline checks with isolated Firebase only."""
from pathlib import Path
from datetime import datetime,timezone
import urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
chart=urllib.request.urlopen('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js').read()
fixture=(ROOT/'tests/firebase-fixture.js').read_text()+'''
(()=>{
 const saved=localStorage.getItem('fixture_summary_store');
 if(saved){for(const [k,v] of JSON.parse(saved))fixture.store.set(k,v);}
 else{
  fixture.store.set('users/alice/calendar/2026-9-20',{muscles:['하체'],confirmed:true});
  fixture.store.set('users/alice/calendar/2026-9-30',{muscles:['하체'],confirmed:true});
  fixture.store.set('users/alice/calendar/2026-10-1',{muscles:['가슴'],confirmed:true});
 }
 fixture.setOnline(localStorage.getItem('fixture_offline')!=='1');
})();
'''
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 def route(r):
  if '/firebase-app.js' in r.request.url:r.fulfill(body=fixture,content_type='application/javascript')
  elif 'firebasejs/' in r.request.url:r.fulfill(body='',content_type='application/javascript')
  elif 'chart.js' in r.request.url:r.fulfill(body=chart,content_type='application/javascript')
  else:r.abort()
 c.route('https://**/*',route)
 c.add_init_script("if(!localStorage.getItem('mf_data_owner_v2')){localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');}")
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.clock.set_fixed_time(datetime(2026,10,10,3,tzinfo=timezone.utc))
 page.goto('http://127.0.0.1:8000/');page.wait_for_timeout(700)
 def leg():return page.locator('#homePartsRow .home-part-item').filter(has=page.locator('.home-part-name',has_text='하체')).locator('.home-part-days').inner_text()
 def persist():page.evaluate("localStorage.setItem('fixture_summary_store',JSON.stringify([...fixture.store]))")
 assert leg()=='10일',page.locator('#homePartsRow').inner_text()
 assert page.evaluate("calData['2026-9-30']") is None
 assert page.evaluate("fixture.calls.filter(c=>c.type==='query'&&c.path==='users/alice/calendar'&&c.filters.length===0).length")==1
 assert page.evaluate("fixture.store.get('users/alice/meta/lastWorkoutDatesV1').latest['하체']")=='2026-09-30'
 # A new device/cache reads only the single server summary, not past calendar months.
 persist();page.evaluate("for(const k of Object.keys(localStorage))if(k.startsWith('mf_account_v2:alice:'))localStorage.removeItem(k)")
 page.reload();page.wait_for_timeout(700)
 assert leg()=='10일'
 assert page.evaluate("fixture.calls.filter(c=>c.type==='get'&&c.path==='users/alice/meta/lastWorkoutDatesV1').length")==1
 assert page.evaluate("fixture.calls.filter(c=>c.type==='query'&&c.path==='users/alice/calendar'&&c.filters.length===0).length")==0
 # Home/tab switching never triggers another summary read.
 for tab in ['tab2','tab1','tab4','tab1']:
  page.locator(f'.bottomTab .tabBtn[data-target="{tab}"]').click();page.wait_for_timeout(50)
 assert page.evaluate("fixture.calls.filter(c=>c.type==='get'&&c.path==='users/alice/meta/lastWorkoutDatesV1').length")==1
 page.evaluate("fixture.setOnline(false);localStorage.setItem('fixture_offline','1')")
 page.evaluate("autoMarkCalendarToday('leg')");page.wait_for_timeout(200)
 assert leg()=='0일'
 assert page.evaluate("fixture.store.get('users/alice/meta/lastWorkoutDatesV1').latest['하체']")=='2026-09-30'
 persist();page.reload();page.wait_for_timeout(700)
 assert leg()=='0일'
 # Reconnect and atomically acknowledge the queued calendar + summary.
 page.evaluate("fixture.setOnline(true);localStorage.removeItem('fixture_offline');window.dispatchEvent(new Event('online'))")
 page.wait_for_timeout(600)
 assert page.evaluate("Object.keys(appSync.outbox.read('alice').ops).length")==0
 assert page.evaluate("fixture.store.get('users/alice/meta/lastWorkoutDatesV1').latest['하체']")=='2026-10-10'
 # Delete latest/change its predecessor offline: previous dates stay available locally.
 page.evaluate("fixture.setOnline(false);privateWrite('alice','calendar','2026-10-10',null)");page.wait_for_timeout(100)
 assert leg()=='10일'
 page.evaluate("privateWrite('alice','calendar','2026-9-30',{muscles:['가슴'],confirmed:true})");page.wait_for_timeout(100)
 assert leg()=='20일'
 page.evaluate("fixture.setOnline(true);window.dispatchEvent(new Event('online'))");page.wait_for_timeout(600)
 assert page.evaluate("fixture.store.has('users/alice/calendar/2026-10-10')") is False
 assert page.evaluate("fixture.store.get('users/alice/meta/lastWorkoutDatesV1').latest['하체']")=='2026-09-20'
 assert page.evaluate("fixture.calls.filter(c=>c.type==='query'&&c.path==='users/alice/calendar'&&c.filters.length===0).length")==0
 for light in [False,True]:
  page.evaluate('(v)=>applyLightMode(v)',light)
  assert leg()=='20일'
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 # Other accounts cannot see Alice's cached summary.
 persist();page.evaluate("localStorage.setItem('fixture_uid','bob')")
 page.reload();page.wait_for_timeout(900)
 assert leg()=='-'
 assert page.evaluate("fixture.calls.filter(c=>c.path==='users/alice/meta/lastWorkoutDatesV1').length")==0
 assert page.evaluate("localStorage.getItem('mf_account_v2:alice:last_workout_dates_v1')") is not None
 assert not errors,errors
 print('PASS: prior-month day count without opening calendar, one-document restart reads, no tab-switch reads, offline save/restart/delete/edit/reconnect, dark/light and account isolation')
 b.close()
