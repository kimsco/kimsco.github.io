const {test}=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('../js/push-devices.js');
function fixture(){
 const data=new Map(),events=[],writes=[],removes=[];
 const f={uid:'alice',permitted:true,online:true,time:1000000,token:'token-a',generation:0};
 f.storage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};
 f.registry=create({storage:f.storage,currentUid:()=>f.uid,allowed:()=>f.permitted,online:()=>f.online,now:()=>f.time,makeId:()=> 'device-1',platform:()=> 'ios',hashToken:async value=>'hash-'+value,
  prepareToken:async()=>{events.push('token');if(f.prepare)return f.prepare();return f.token;},
  unsubscribe:async()=>{events.push('unsubscribe');if(f.failUnsubscribe)throw Error('offline');f.token='token-'+(++f.generation);},
  saveDevice:async(uid,id,record)=>{events.push('save:'+uid);if(f.save)await f.save();writes.push({uid,id,record});},
  removeDevice:async(uid,id)=>{events.push('remove:'+uid);removes.push({uid,id});}
 });return Object.assign(f,{data,events,writes,removes});
}
test('register once without reads and cache only a token fingerprint',async()=>{
 const f=fixture();assert.equal(await f.registry.sync(),true);assert.equal(f.writes.length,1);
 assert.deepEqual(f.writes[0],{uid:'alice',id:'device-1',record:{token:'token-a',enabled:true,platform:'ios'}});
 assert.ok(![...f.data.values()].some(value=>value.includes('"token":')));
 await f.registry.sync();assert.equal(f.writes.length,1);
 f.time+=7*24*60*60*1000;await f.registry.sync();assert.equal(f.writes.length,2);
});
test('token rotation updates the same device document',async()=>{
 const f=fixture();await f.registry.sync();f.token='rotated';await f.registry.sync();assert.equal(f.writes.length,2);assert.equal(f.writes[1].id,'device-1');assert.equal(f.writes[1].record.token,'rotated');
});
test('logout revokes subscription and removes the current account device',async()=>{
 const f=fixture();await f.registry.sync();await f.registry.detach();assert.deepEqual(f.removes,[{uid:'alice',id:'device-1'}]);assert.equal(f.storage.getItem('mf_push_binding_v1'),null);
 f.uid=null;await f.registry.accountChanged();assert.equal(f.writes.length,1);
});
test('account switch rotates before registering and never deletes another account with new credentials',async()=>{
 const f=fixture();await f.registry.sync();f.events.length=0;f.uid='bob';await f.registry.accountChanged();assert.deepEqual(f.events,['unsubscribe','token','save:bob']);assert.equal(f.removes.length,0);assert.notEqual(f.writes[0].record.token,f.writes[1].record.token);
});
test('failed logout persists rotation requirement and cannot register the old token to a new account',async()=>{
 const f=fixture();await f.registry.sync();f.failUnsubscribe=true;await assert.rejects(f.registry.detach());
 assert.equal(JSON.parse(f.storage.getItem('mf_push_binding_v1')).needsRotation,true);
 f.uid='bob';await assert.rejects(f.registry.accountChanged());assert.equal(f.writes.length,1);
 f.failUnsubscribe=false;await f.registry.sync();assert.equal(f.writes.length,2);assert.equal(f.writes[1].uid,'bob');
});
test('permission revocation removes the device and does not obtain a token',async()=>{
 const f=fixture();await f.registry.sync();f.events.length=0;f.permitted=false;await f.registry.sync();assert.deepEqual(f.events,['unsubscribe','remove:alice']);
});
test('guests and offline sessions do not register devices',async()=>{
 const f=fixture();assert.equal(f.registry.isRegistered(),false);f.uid=null;await f.registry.sync();assert.equal(f.events.length,0);f.uid='alice';f.online=false;await f.registry.sync();assert.equal(f.events.length,0);assert.equal(f.registry.isRegistered(),false);
});
test('a late token response cannot write after logout and cleanup remains ordered',async()=>{
 const f=fixture();let resolve,started;const ready=new Promise(r=>started=r);f.prepare=()=>{started();return new Promise(r=>resolve=r);};
 const registration=f.registry.sync();await ready;const detach=f.registry.detach();resolve('late-token');await registration;await detach;assert.equal(f.writes.length,0);assert.equal(f.events.at(-2),'unsubscribe');
});
test('an in-flight write finishes before logout deletes, and cannot recreate a device',async()=>{
 const f=fixture();let finish,started;const ready=new Promise(r=>started=r);f.save=()=>{started();return new Promise(r=>finish=r);};
 const registration=f.registry.sync();await ready;const detach=f.registry.detach();finish();await registration;await detach;
 assert.equal(f.events.at(-1),'remove:alice');assert.equal(f.storage.getItem('mf_account_v2:alice:push_device_ack'),null);
});
test('an account switch during token issuance rotates the stale token before the new account write',async()=>{
 const f=fixture();let resolve,started;const ready=new Promise(r=>started=r);f.prepare=()=>{started();return new Promise(r=>resolve=r);};
 const first=f.registry.sync();await ready;f.uid='bob';f.prepare=null;const second=f.registry.accountChanged();resolve('token-for-old-session');await first;await second;
 assert.equal(f.writes.length,1);assert.equal(f.writes[0].uid,'bob');assert.ok(f.events.indexOf('unsubscribe')<f.events.indexOf('save:bob'));
});
test('offline account switch cannot mark another account registered',async()=>{
 const f=fixture();await f.registry.sync();assert.equal(f.registry.isRegistered(),true);f.uid='bob';f.online=false;await f.registry.accountChanged();assert.equal(f.registry.isRegistered(),false);
});
