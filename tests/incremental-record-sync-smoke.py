"""Two isolated phones, unchanged/read budgets, single-write stamps and tombstones."""
from pathlib import Path
import subprocess,sys,time
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
fixture=(root/'tests/firebase-fixture.js').read_text().replace('  window.fixture={',"""  store.set('users/alice/records/old',{lift:'bench',date:'20.01.01',weight:60,reps:5,createdAt:1});
 for(let i=0;i<100;i++)store.set('users/alice/accessoryRecords/old-'+i,{exercise:'Press',part:'chest',date:'20.01.01',weight:20,reps:8,createdAt:1});
 window.fixture={""",1)
server=subprocess.Popen([sys.executable,'-m','http.server','8196','--bind','127.0.0.1'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.3)
 with sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);errors=[]
  def phone():
   c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
   c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');")
   c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
   p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto('http://127.0.0.1:8196/');p.wait_for_function("!workoutSyncPending && accRecordsByExercise.Press?.length===100")
   return c,p
  ca,a=phone();cb,p=phone()
  calls="fixture.calls.filter(x=>x.rest)"
  before=p.evaluate(calls+'.length');p.evaluate('syncWorkoutRecords({force:true})')
  assert p.evaluate(calls+'.length')==before+2
  assert p.evaluate(calls+'.slice(-2).every(x=>x.returnedDocuments===0)')
  assert p.locator('#manualRecordSyncBtn').count()==0
  # A changes its original documents once each; no extra change or head documents.
  a.evaluate("""async()=>{for(let i=0;i<20;i++)await appSync.write('alice','accessoryRecords','new-'+i,{exercise:'Press',part:'chest',date:'26.10.21',weight:30,reps:8,createdAt:Date.now()});while(Object.keys(appSync.outbox.read('alice').ops).length)await new Promise(r=>setTimeout(r,5));}""")
  assert a.evaluate("fixture.calls.filter(x=>x.type==='set' && x.path.includes('/accessoryRecords/new-')).length")==20
  assert not a.evaluate("fixture.calls.some(x=>x.path.includes('recordUpdates'))")
  def copy_records(source,target):
   data=source.evaluate(r"""()=>[...fixture.store].filter(([k])=>/users\/alice\/(records|accessoryRecords)\//.test(k)).map(([k,d])=>[k,Object.fromEntries(Object.entries(d).map(([f,v])=>[f,v?.toMillis?{__timestamp:v.toMillis()}:v]))])""")
   target.evaluate(r"""rows=>{for(const key of fixture.store.keys())if(/users\/alice\/(records|accessoryRecords)\//.test(key))fixture.store.delete(key);for(const [key,data]of rows)fixture.store.set(key,Object.fromEntries(Object.entries(data).map(([f,v])=>[f,v?.__timestamp!==undefined?firebase.firestore.Timestamp.fromMillis(v.__timestamp):v])));}""",data)
  copy_records(a,p);p.evaluate('syncWorkoutRecords({force:true})')
  assert p.evaluate('accRecordsByExercise.Press.length')==120
  assert p.evaluate(calls+'.slice(-2).reduce((sum,x)=>sum+Math.max(1,x.returnedDocuments),0)')==21
  a.evaluate("""async()=>{await appSync.write('alice','records','old',{weight:65},{merge:true});await appSync.write('alice','accessoryRecords','old-0',null);while(Object.keys(appSync.outbox.read('alice').ops).length)await new Promise(r=>setTimeout(r,5));}""")
  assert a.evaluate("fixture.store.get('users/alice/accessoryRecords/old-0').deleted===true")
  assert not a.evaluate("fixture.calls.some(x=>x.type==='delete' && x.path==='users/alice/accessoryRecords/old-0')")
  copy_records(a,p);p.evaluate('syncWorkoutRecords({force:true})')
  assert p.evaluate("records.bench[0].weight===65 && accRecordsByExercise.Press.length===119")
  assert p.evaluate(calls+'.slice(-2).reduce((sum,x)=>sum+Math.max(1,x.returnedDocuments),0)')==2
  # Reload keeps local baseline; only two empty server queries remain.
  p.reload();p.wait_for_function("!workoutSyncPending && fixture.calls.filter(x=>x.rest).length===2")
  assert p.evaluate('accRecordsByExercise.Press.length')==119
  assert p.evaluate(calls+'.every(x=>x.returnedDocuments===0)')
  # Local writes accepted while a snapshot is in flight win even after server acknowledgement.
  p.evaluate("()=>{window.fixtureQueryGate=new Promise(r=>window.releaseQuery=r);window.pendingSync=syncWorkoutRecords({force:true});}")
  p.wait_for_timeout(50)
  p.evaluate("""async()=>{await appSync.write('alice','records','late',{lift:'bench',date:'26.10.21',weight:90,reps:5,createdAt:Date.now()});while(Object.keys(appSync.outbox.read('alice').ops).length)await new Promise(r=>setTimeout(r,5));}""")
  p.evaluate('releaseQuery();fixtureQueryGate=null;pendingSync')
  assert p.evaluate("records.bench.some(row=>row.firestoreId==='late' && row.weight===90)")
  # Failed reads preserve data/checkpoints; a successful retry receives the remote row.
  saved=p.evaluate("localStorage.getItem('mf_account_v2:alice:record_sync_v1:records')")
  p.evaluate("fixture.changeRecord('records','later',{lift:'squat',date:'26.10.21',weight:100,reps:3,createdAt:1});fixture.setDenied(true)")
  assert p.evaluate('syncWorkoutRecords({force:true})') is False
  assert p.evaluate("localStorage.getItem('mf_account_v2:alice:record_sync_v1:records')")==saved
  p.evaluate('fixture.setDenied(false);syncWorkoutRecords({force:true})')
  assert p.evaluate("records.squat.some(row=>row.firestoreId==='later')")
  # A storage failure cannot mark remote changes as received.
  old_weight=p.evaluate("records.bench.find(row=>row.firestoreId==='old').weight")
  saved=p.evaluate("localStorage.getItem('mf_account_v2:alice:record_sync_v1:records')")
  p.evaluate("()=>{fixture.changeRecord('records','old',{weight:77});window.originalAccSave=saveAccRecordsToLocal;saveAccRecordsToLocal=()=>{throw Error('quota')};}")
  assert p.evaluate('syncWorkoutRecords({force:true})') is False
  assert p.evaluate("records.bench.find(row=>row.firestoreId==='old').weight")==old_weight
  assert p.evaluate("localStorage.getItem('mf_account_v2:alice:record_sync_v1:records')")==saved
  p.evaluate('saveAccRecordsToLocal=originalAccSave;syncWorkoutRecords({force:true})')
  assert p.evaluate("records.bench.find(row=>row.firestoreId==='old').weight")==77
  # A newer remote edit can revive an acknowledged old local deletion.
  p.evaluate("""async()=>{await appSync.write('alice','records','old',null);while(Object.keys(appSync.outbox.read('alice').ops).length)await new Promise(r=>setTimeout(r,5));await syncWorkoutRecords({force:true});}""")
  assert p.evaluate("!records.bench.some(row=>row.firestoreId==='old')")
  p.evaluate("fixture.changeRecord('records','old',{weight:80,deleted:false});syncWorkoutRecords({force:true})")
  assert p.evaluate("records.bench.find(row=>row.firestoreId==='old').weight")==80
  # A switched account cannot receive an old account's in-flight response.
  p.evaluate("()=>{window.fixtureQueryGate=new Promise(r=>window.releaseQuery=r);window.switchedSync=syncWorkoutRecords({force:true});}")
  p.wait_for_timeout(30)
  p.evaluate("fixture.auth.currentUser={uid:'bob',getIdToken:async()=> 'fixture-token'};appSync.account.select('bob','bob@example.test');releaseQuery();fixtureQueryGate=null")
  assert p.evaluate('switchedSync') is False
  assert p.evaluate("localStorage.getItem('mf_account_v2:bob:record_sync_v1:records')") is None
  assert not errors,errors
  ca.close();cb.close();b.close()
 print('PASS: two phones receive only changes; no changes=2 reads; 20 accessory additions=21; writes=1 per original; tombstones, reload, pending writes, failure and account isolation')
finally:server.terminate();server.wait()
