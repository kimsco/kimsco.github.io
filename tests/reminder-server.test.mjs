import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {createStore, runReminder, koreaDay, TEXT} from '../reminder-server/core.mjs';
import {createHandler, validSubscription, push} from '../reminder-server/worker.mjs';
import {buildPushPayload} from '../reminder-server/node_modules/@block65/webcrypto-web-push/dist/lib/main.js';
const TIME = Date.parse('2026-10-27T13:00:00Z'), DAY = '2026-10-27', BASIS = '2026-10-27T12:59:00.000000001Z';
const b64 = bytes => Buffer.from(bytes).toString('base64url');
const subscription = id => ({endpoint: 'https://web.push.apple.com/' + id, keys: {p256dh: b64([4, ...new Uint8Array(64)]), auth: b64(new Uint8Array(16))}});
function fixture() {
 const sqlite = new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('../reminder-server/schema.sql',import.meta.url),'utf8'));
 function prepare(sql) {
  let values = [];
  const statement = {bind: (...args) => {values=args;return statement;},
   run: async () => {const result=sqlite.prepare(sql).run(...values);return {meta:{changes:Number(result.changes)}};},
   first: async () => sqlite.prepare(sql).get(...values)||null,
   all: async () => ({results:sqlite.prepare(sql).all(...values)})};return statement;
 }
 let batches=Promise.resolve();
 const db = {prepare,batch: statements => {const work=batches.catch(()=>{}).then(async()=>{sqlite.exec('BEGIN');try{const values=[];for(const s of statements)values.push(await s.run());sqlite.exec('COMMIT');return values;}catch(error){sqlite.exec('ROLLBACK');throw error;}});batches=work;return work;}};
 const store=createStore(db), sent=[];
 const send=async(sub,payload)=>{sent.push({sub,payload});return {status:201};};
 const run=(overrides={})=>runReminder({store,send,time:TIME,enabled:true,...overrides});
 return {store,db,sqlite,sent,send,run};
}
test('Korean day boundary is independent of server timezone',()=>{
 assert.equal(koreaDay(Date.parse('2026-10-27T14:59:59Z')),'2026-10-27');
 assert.equal(koreaDay(Date.parse('2026-10-27T15:00:00Z')),'2026-10-28');
});
test('22:00 sends exact message only to initialized users without real records',async()=>{
 const f=fixture();for(const uid of ['inactive','active','unknown'])await f.store.register(uid,'phone',subscription(uid));
 await f.store.activity('inactive',DAY,false,BASIS);await f.store.activity('active',DAY,true,BASIS);
 const result=await f.run();assert.equal(result.accepted,1);assert.equal(f.sent[0].payload.data.receiverUid,'inactive');
 assert.equal(f.sent[0].payload.notification.title,'');assert.equal(f.sent[0].payload.notification.body,TEXT);assert.ok(!JSON.stringify(f.sent).includes('active/'));
});
test('unconfigured/off-hours schedule never sends',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 await f.run({enabled:false});await f.run({time:TIME-3600000});assert.equal(f.sent.length,0);
});
test('different users receive at their own selected Korea time, including midnight',async()=>{
 const f=fixture();for(const uid of ['early','default','midnight']){await f.store.register(uid,'p',subscription(uid));await f.store.activity(uid,DAY,false,BASIS);}
 await f.store.savePreference('early',21*60+15);await f.store.savePreference('midnight',0);
 assert.equal((await f.run({time:Date.parse('2026-10-26T15:00:00Z')})).accepted,1);
 assert.equal(f.sent.at(-1).payload.data.receiverUid,'midnight');
 assert.equal((await f.run({time:Date.parse('2026-10-27T12:14:00Z')})).accepted,0);
 assert.equal((await f.run({time:Date.parse('2026-10-27T12:15:00Z')})).accepted,1);
 assert.equal(f.sent.at(-1).payload.data.receiverUid,'early');
 assert.equal((await f.run()).accepted,1);assert.equal(f.sent.at(-1).payload.data.receiverUid,'default');
});
test('time change between eligibility and reservation prevents an early send',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 const [candidate]=await f.store.eligible(DAY,1320);await f.store.savePreference('u',1380);
 assert.equal(await f.store.claim(candidate,DAY,1320),null);assert.equal((await f.run()).accepted,0);
 assert.equal((await f.run({time:TIME+3600000})).accepted,1);
});
test('saving a time already passed starts tomorrow rather than sending immediately',async()=>{
 const f=fixture(),handler=createHandler({verify:async()=> 'u',now:()=>TIME});
 await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 const response=await handler(new Request('https://worker.test/preferences',{method:'PUT',headers:{Origin:'https://kimsco.github.io'},body:JSON.stringify({minuteOfDay:1310})}),{DB:f.db});
 assert.equal(response.status,200);assert.equal((await f.run()).accepted,0);
 assert.equal((await f.run({time:TIME+86400000-600000})).accepted,1);
});
test('prior-day workout does not suppress today; unopened initialized app can receive',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u','2026-10-26',true,'2026-10-26T12:00:00Z');
 assert.equal((await f.run()).accepted,1);
});
test('last set deletion reverses true, while older other-phone updates cannot overwrite it',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,true,BASIS);
 assert.equal((await f.run()).accepted,0);
 await f.store.activity('u',DAY,false,'2026-10-27T12:59:01.000000001Z');
 await f.store.activity('u',DAY,true,'2026-10-27T12:59:00.999999999Z');
 assert.equal((await f.run()).accepted,1);
});
test('a local bodyweight routine on one phone cannot be erased by another phones cloud-record summary',async()=>{
 const f=fixture();await f.store.register('u','iphone',subscription('a'));
 await f.store.activity('u',DAY,false,BASIS,'first-phone',true);
 await f.store.activity('u',DAY,false,'2026-10-27T12:59:01Z','second-phone',false);
 assert.equal((await f.run()).accepted,0);
 await f.store.activity('u',DAY,false,'2026-10-27T12:59:02Z','first-phone',false);
 assert.equal((await f.run()).accepted,1);
});
test('same device/day/time is delivered once across repeated/concurrent jobs and reconnects',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 await Promise.all([f.run(),f.run()]);await f.store.register('u','p',subscription('new'));await f.run();assert.equal(f.sent.length,1);
});
test('registration and final pre-send activity check are atomic with eligibility',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 const [candidate]=await f.store.eligible(DAY);
 await f.store.activity('u',DAY,true,'2026-10-27T12:59:02Z');assert.equal(await f.store.claim(candidate,DAY),null);
 await f.store.activity('u',DAY,false,'2026-10-27T12:59:03Z');await f.store.register('u','p',subscription('rotated'));
 assert.equal(await f.store.claim(candidate,DAY),null);
});
test('expired endpoints are removed but transient failures are neither deleted nor resent',async()=>{
 for(const status of [410,404,503]){
  const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
  await f.run({send:async()=>({status})});await f.run();assert.equal(f.sent.length,0);
  assert.equal((await f.db.prepare('SELECT COUNT(*) AS n FROM devices').first()).n,status===503?1:0);
 }
});
test('each minute drains next batch without duplicating first ten devices',async()=>{
 const f=fixture();for(let i=0;i<13;i++){await f.store.register('u'+i,'p',subscription(i));await f.store.activity('u'+i,DAY,false,BASIS);}
 assert.equal((await f.run()).accepted,10);assert.equal((await f.run({time:TIME+60000})).accepted,3);assert.equal((await f.run({time:TIME+120000})).accepted,0);
});
test('API takes UID only from verified token and rejects personal record fields',async()=>{
 const f=fixture(), handler=createHandler({verify:async()=> 'alice',now:()=>TIME});
 const request=(path,body,method='POST')=>new Request('https://worker.test'+path,{method,headers:{Origin:'https://kimsco.github.io','Content-Type':'application/json',Authorization:'Bearer test'},body:JSON.stringify(body)});
 assert.equal((await handler(request('/activity',{day:DAY,hasRecord:true,basis:BASIS,weight:50}),{DB:f.db})).status,400);
 assert.equal((await handler(request('/activity',{day:DAY,hasRecord:true,basis:BASIS}),{DB:f.db})).status,200);
 assert.equal((await f.db.prepare('SELECT uid FROM activity').first()).uid,'alice');
 assert.equal((await handler(request('/activity',{day:'2026-10-26',hasRecord:false,basis:BASIS}),{DB:f.db})).status,400);
 const denied=createHandler({verify:async()=>{throw Error('bad token');}});
 assert.equal((await denied(request('/activity',{}),{DB:f.db})).status,401);
 assert.equal((await handler(new Request('https://worker.test/config',{headers:{Origin:'https://evil.test'}}),{DB:f.db})).status,403);
});
test('API removes only the authenticated users device and supports account erasure',async()=>{
 const f=fixture(), handler=createHandler({verify:async()=> 'alice',now:()=>TIME});
 await f.store.register('alice','p',subscription('alice'));await f.store.register('bob','p',subscription('bob'));await f.store.activity('alice',DAY,true,BASIS);
 const request=(path,body)=>new Request('https://worker.test'+path,{method:'DELETE',headers:{Origin:'https://kimsco.github.io'},body:body?JSON.stringify(body):undefined});
 assert.equal((await handler(request('/device',{id:'p'}),{DB:f.db})).status,200);
 assert.equal((await f.db.prepare('SELECT uid FROM devices').first()).uid,'bob');
 await handler(request('/account'),{DB:f.db});assert.equal((await f.db.prepare('SELECT COUNT(*) AS n FROM activity').first()).n,0);
});
test('preference API validates minutes, isolates UID, and account deletion clears the preference',async()=>{
 const f=fixture(),handler=createHandler({verify:async()=> 'alice'});
 const request=(method,body)=>new Request('https://worker.test/preferences',{method,headers:{Origin:'https://kimsco.github.io'},body:body===undefined?undefined:JSON.stringify(body)});
 assert.equal((await (await handler(request('GET'),{DB:f.db})).json()).minuteOfDay,1320);
 assert.equal((await handler(request('PUT',{minuteOfDay:1385}),{DB:f.db})).status,200);
 assert.equal((await f.store.preference('alice')).minuteOfDay,1385);assert.equal((await f.store.preference('bob')).minuteOfDay,1320);
 for(const minute of [-1,1440,2.5,'100'])assert.equal((await handler(request('PUT',{minuteOfDay:minute}),{DB:f.db})).status,400);
 assert.equal((await handler(request('PUT',{minuteOfDay:100,uid:'bob'}),{DB:f.db})).status,400);
 await f.store.forget('alice');assert.equal((await f.store.preference('alice')).minuteOfDay,1320);
});
test('subscription validation forbids arbitrary hosts/credentials/ports and malformed keys',()=>{
 assert.equal(validSubscription(subscription('a')).endpoint,subscription('a').endpoint);
 for(const endpoint of ['http://web.push.apple.com/x','https://localhost/x','https://web.push.apple.com.evil.test/x','https://u:p@web.push.apple.com/x','https://web.push.apple.com:8443/x'])assert.throws(()=>validSubscription({...subscription('a'),endpoint}));
 assert.throws(()=>validSubscription({...subscription('a'),keys:{p256dh:'bad',auth:'bad'}}));
});
test('public configuration verifies matching keys and never reveals the private key',async()=>{
 const f=fixture(),handler=createHandler();
 const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']);
 const key=await crypto.subtle.exportKey('jwk',pair.privateKey),publicKey=b64(await crypto.subtle.exportKey('raw',pair.publicKey));
 const request=()=>new Request('https://worker.test/config',{headers:{Origin:'https://kimsco.github.io'}});
 const response=await handler(request(),{DB:f.db,VAPID_PUBLIC_KEY:publicKey,VAPID_PRIVATE_KEY:key.d}),result=await response.json();
 assert.equal(result.ready,true);assert.equal(result.publicKey,publicKey);assert.ok(!JSON.stringify(result).includes(key.d));
 const broken=await handler(request(),{DB:f.db,VAPID_PUBLIC_KEY:publicKey,VAPID_PRIVATE_KEY:'bad'});assert.equal((await broken.json()).ready,false);
});
test('real Web Push library generates Apple-compatible aes128gcm payload and VAPID auth',async()=>{
 const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']);
 const privateKey=await crypto.subtle.exportKey('jwk',pair.privateKey),publicKey=await crypto.subtle.exportKey('raw',pair.publicKey);
 const receiver=await crypto.subtle.generateKey({name:'ECDH',namedCurve:'P-256'},true,['deriveBits']);
 const sub={endpoint:'https://web.push.apple.com/test',keys:{p256dh:b64(await crypto.subtle.exportKey('raw',receiver.publicKey)),auth:b64(crypto.getRandomValues(new Uint8Array(16)))}};
 const payload=await buildPushPayload({data:JSON.stringify({notification:{body:TEXT}}),options:{ttl:3600,urgency:'high'}},sub,{subject:'https://kimsco.github.io',publicKey:b64(publicKey),privateKey:privateKey.d});
 assert.equal(payload.headers['content-encoding'],'aes128gcm');assert.match(payload.headers.authorization,/^vapid t=/);assert.equal(payload.headers.ttl,'3600');assert.equal(payload.body.length,4096);
});

test('send diagnostics distinguish preparation and fetch failures without exposing secrets',async()=>{
 const original=console.error,logs=[];console.error=value=>logs.push(value);
 try{
  for(const stage of ['prepare','fetch']){
   const secret='private-key-and-endpoint',error=new TypeError(secret);
   await assert.rejects(push({},subscription('secret'),{}, {
    build:async()=>{if(stage==='prepare')throw error;return {};},send:async()=>{throw error;}
   }),value=>value.reminderFailure==='failed-'+stage+'-TypeError');
   const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
   await f.run({send:async()=>{const failure=new Error(secret);failure.reminderFailure='failed-'+stage+'-TypeError';throw failure;}});
   assert.equal(f.sqlite.prepare('SELECT status FROM delivery_slots').get().status,'failed-'+stage+'-TypeError');
  }
  assert.equal(logs.length,2);assert.ok(!logs.join('').includes('private-key-and-endpoint'));assert.ok(!logs.join('').includes('web.push.apple.com'));
 }finally{console.error=original;}
});

test('Workers sender uses manual redirects and never follows a different endpoint',async()=>{
 let called=0;
 const result=await push({},subscription('a'),{}, {build:async()=>({method:'POST',body:new Uint8Array([1])}),send:async(url,init)=>{
  called++;assert.equal(url,'https://web.push.apple.com/a');assert.equal(init.redirect,'manual');return {status:302};
 }});
 assert.equal(called,1);assert.equal(result.status,302);
});
test('a new future time sends again today, while unchanged/repeated time stays deduplicated',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 assert.equal((await f.run()).accepted,1);
 await f.store.savePreference('u',1330,DAY);
 assert.equal((await f.run()).accepted,0);
 assert.equal((await f.run({time:TIME+600000})).accepted,1);
 await f.store.savePreference('u',1330,DAY);
 await Promise.all([f.run({time:TIME+600000}),f.run({time:TIME+660000})]);
 assert.equal(f.sent.length,2);
 assert.notEqual(f.sent[0].payload.messageId,f.sent[1].payload.messageId);
 await f.store.savePreference('u',1320,DAY);
 assert.equal((await f.run({time:TIME+720000})).accepted,0);
 assert.deepEqual(f.sqlite.prepare('SELECT minute_of_day,status FROM delivery_slots ORDER BY minute_of_day').all().map(x=>({...x})),[{minute_of_day:1320,status:'accepted'},{minute_of_day:1330,status:'accepted'}]);
});
test('a real workout suppresses a newly selected time even after an earlier notification',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);await f.run();
 await f.store.savePreference('u',1330,DAY);await f.store.activity('u',DAY,true,'2026-10-27T13:05:00Z');
 assert.equal((await f.run({time:TIME+600000})).accepted,0);assert.equal(f.sent.length,1);
});
test('switching to another due time invalidates stale candidates even within the catch-up window',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 const [candidate]=await f.store.eligible(DAY,1330);
 await f.store.savePreference('u',1325,DAY);
 assert.equal(await f.store.claim(candidate,DAY,1330),null);
 assert.equal((await f.run({time:TIME+600000})).accepted,1);
 assert.equal(f.sqlite.prepare('SELECT minute_of_day FROM delivery_slots').get().minute_of_day,1325);
});
test('an in-flight send finishes its original time slot after preferences change',async()=>{
 const f=fixture();await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 await f.run({send:async()=>{await f.store.savePreference('u',1330,DAY);return {status:201};}});
 assert.equal((await f.run({time:TIME+600000})).accepted,1);
 assert.equal(f.sqlite.prepare("SELECT COUNT(*) AS n FROM delivery_slots WHERE status='accepted'").get().n,2);
});
test('migration keeps legacy history and treats the current setting as handled only once',async()=>{
 const f=fixture(),migration=readFileSync(new URL('../reminder-server/migrate-per-time.sql',import.meta.url),'utf8');
 await f.store.register('u','p',subscription('a'));await f.store.activity('u',DAY,false,BASIS);
 f.sqlite.prepare('INSERT INTO deliveries(uid,device_id,day,status) VALUES(?,?,?,?)').run('u','p',DAY,'accepted');
 f.sqlite.exec(migration);assert.equal((await f.run()).accepted,0);
 await f.store.savePreference('u',1330,DAY);f.sqlite.exec(migration);
 assert.equal((await f.run({time:TIME+600000})).accepted,1);
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) AS n FROM deliveries').get().n,1);
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) AS n FROM delivery_slots').get().n,2);
 await f.store.forget('u');assert.equal(f.sqlite.prepare('SELECT COUNT(*) AS n FROM delivery_slots').get().n,0);
});
test('pruning removes old time slots but preserves recent delivery history',async()=>{
 const f=fixture();
 for(const day of ['2026-10-01',DAY])f.sqlite.prepare('INSERT INTO delivery_slots VALUES(?,?,?,?,?)').run('u','p',day,1320,'accepted');
 await f.store.prune(DAY);
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) AS n FROM delivery_slots').get().n,1);
 assert.equal(f.sqlite.prepare('SELECT day FROM delivery_slots').get().day,DAY);
});
