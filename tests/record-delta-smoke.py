"""Persistent isolated backend: warm restart, metadata-only checks and delta updates."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text()
fixture=fixture.replace('  window.fixture={',"""  if(!store.has('users/alice/meta/recordSync')){
  const t=new Date(),day=String(t.getFullYear()).slice(-2)+'.'+String(t.getMonth()+1).padStart(2,'0')+'.'+String(t.getDate()).padStart(2,'0');
  store.set('users/alice/accessories/chest',{list:['Chest press']});
  store.set('users/alice/records/bench-one',{lift:'bench',date:day,weight:90,reps:5,createdAt:Date.now()-10000});
  for(let i=0;i<100;i++)store.set('users/alice/accessoryRecords/record-'+i,{exercise:'Chest press',part:'chest',date:day,weight:60,reps:5,createdAt:Date.now()-10000});
  }
  window.fixture={""",1)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844},is_mobile=True)
 c.add_init_script("localStorage.setItem('fixture_uid','alice');localStorage.setItem('mf_data_owner_v2','alice');localStorage.setItem('mf_legacy_migrated_v2','1');localStorage.setItem('fixture_persist_server','1');")
 c.route('https://**/*',lambda r:r.fulfill(body=fixture if '/firebase-app-compat.js' in r.request.url else '',content_type='application/javascript'))
 page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/');page.wait_for_function("appSync.recordChanges.readCursor('alice')?.version===0 && accRecordsByExercise['Chest press']?.length===100 && records.bench.length===1")
 page.wait_for_function("isFullSyncFresh('alice')")
 page.reload();page.wait_for_function("appSync.recordChanges.readCursor('alice')?.version===0 && accRecordsByExercise['Chest press']?.length===100")
 page.wait_for_timeout(200)
 bulk="fixture.calls.filter(x=>x.type==='query' && ['users/alice/records','users/alice/accessoryRecords'].includes(x.path)).length"
 assert page.evaluate(bulk)==0
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/meta/recordSync' && x.type==='get').length")==1
 page.evaluate("window.remote=MFRecordChanges.createService({db,storage:{getItem:()=>null,setItem:()=>{}},currentUid:()=> 'alice',clean:value=>JSON.parse(JSON.stringify(value,(_,v)=>v?.toMillis?.()??v))})")
 page.evaluate("remote.write('alice',{collection:'accessoryRecords',id:'record-0',data:{weight:70},merge:true,clientId:'other-device',clientSeq:1})")
 page.evaluate("window.originalNow=Date.now;Date.now=()=>originalNow()+31000")
 page.evaluate('refreshSyncedRecords()');page.wait_for_function("accRecordsByExercise['Chest press'].find(x=>x.id==='record-0').weight===70")
 assert page.evaluate(bulk)==0
 assert page.evaluate("fixture.calls.filter(x=>x.path==='users/alice/recordChanges' && x.type==='query').length")==1
 page.evaluate("remote.write('alice',{collection:'accessoryRecords',id:'record-1',data:null,clientId:'other-device',clientSeq:2})")
 page.evaluate("Date.now=()=>originalNow()+62000;refreshSyncedRecords()")
 page.wait_for_function("accRecordsByExercise['Chest press'].length===99")
 assert page.evaluate("accRecordsByExercise['Chest press'].some(x=>x.id==='record-1')") is False
 # Offline queue updates the UI immediately and replays atomically after reconnect.
 page.evaluate("fixture.setOnline(false);Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>false})")
 page.evaluate("myRoutineSaveAccessorySet('Chest press','chest',65,8)")
 assert page.evaluate("accRecordsByExercise['Chest press'].length")==100
 assert page.evaluate("Object.keys(appSync.outbox.read('alice').ops).length")>=1
 page.evaluate("fixture.setOnline(true);Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>true})")
 page.evaluate('appSync.outbox.flush()');page.wait_for_function("Object.keys(appSync.outbox.read('alice').ops).length===0")
 page.evaluate('refreshSyncedRecords()');page.wait_for_timeout(150)
 assert page.evaluate("accRecordsByExercise['Chest press'].length")==100
 assert page.evaluate("new Set(accRecordsByExercise['Chest press'].map(x=>x.id)).size")==100
 assert page.evaluate(bulk)==0
 assert not errors,errors
 print('PASS: unchanged warm app reads one record-version document and zero bulk record queries; remote update/delete use delta feed; offline set replay is stable and does not duplicate records')
 b.close()
