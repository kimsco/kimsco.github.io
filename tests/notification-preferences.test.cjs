const {test}=require('node:test');const assert=require('node:assert/strict');
const {createPreferences,DEFAULT_MINUTE}=require('../js/notification-settings.js');
function fixture(){const data=new Map();let uid='alice',counter=0;const storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)};return {data,storage,preferences:createPreferences({storage,currentUid:()=>uid,revision:()=>String(++counter)}),select:value=>uid=value};}
test('default is 22:00; all midnight/noon/end-of-day minute values persist',()=>{
 const f=fixture();assert.equal(f.preferences.read().minuteOfDay,1320);assert.equal(DEFAULT_MINUTE,1320);
 for(const minute of [0,60,720,1320,1439]){f.preferences.save(minute);assert.equal(f.preferences.read().minuteOfDay,minute);assert.equal(f.preferences.read().dirty,true);}
 for(const minute of [-1,1440,1.5,'120',NaN])assert.throws(()=>f.preferences.save(minute));
});
test('guest and different account times are isolated across logins',()=>{
 const f=fixture();f.preferences.save(600);f.select('bob');assert.equal(f.preferences.read().minuteOfDay,1320);
 f.preferences.save(720);f.select(null);assert.equal(f.preferences.read().minuteOfDay,1320);f.preferences.save(900);
 f.select('alice');assert.equal(f.preferences.read().minuteOfDay,600);f.select('bob');assert.equal(f.preferences.read().minuteOfDay,720);
});
test('old synchronization responses cannot acknowledge a newer save or overwrite pending edits',()=>{
 const f=fixture(),first=f.preferences.save(600);f.preferences.save(800);f.preferences.acknowledge(first.revision);
 assert.equal(f.preferences.read().dirty,true);f.preferences.fromServer(1000);assert.equal(f.preferences.read().minuteOfDay,800);
 f.preferences.acknowledge(f.preferences.read().revision);f.preferences.fromServer(1000);assert.equal(f.preferences.read().minuteOfDay,1000);assert.equal(f.preferences.read().dirty,false);
});
test('storage failure is reported rather than returning a successful save',()=>{
 const preferences=createPreferences({storage:{getItem:()=>null,setItem:()=>{throw Error('quota');}},currentUid:()=> 'alice'});
 assert.throws(()=>preferences.save(600),/quota/);
});
