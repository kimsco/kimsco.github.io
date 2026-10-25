const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function fixture(){
 const listeners={},notifications=[],opened=[],receiptStore=new Map();
 const self={location:{origin:'https://example.test'},registration:{showNotification:async(title,options)=>notifications.push({title,...options})},clients:{matchAll:async()=>[],openWindow:async url=>opened.push(url)}};
 self.addEventListener=(name,listener)=>listeners[name]=listener;
 const caches={open:async()=>({put:async(key,value)=>receiptStore.set(key,value),match:async key=>receiptStore.get(key)?.clone()})};
 vm.runInNewContext(fs.readFileSync('sw.js','utf8'),{self,URL,caches,Response});
 return {self,listeners,notifications,opened,receiptStore};
}
test('FCM Web Push shows a notification without Firestore access',async()=>{
 const f=fixture();let work;
 f.listeners.push({data:{json:()=>({notification:{title:'푸시 테스트',body:'앱을 닫고 확인'},fcmOptions:{link:'https://example.test/?push=1'}})},waitUntil:p=>work=p});await work;
 assert.equal(f.notifications.length,1);assert.equal(f.notifications[0].title,'푸시 테스트');assert.equal(f.notifications[0].body,'앱을 닫고 확인');assert.equal(f.notifications[0].data.url,'https://example.test/?push=1');
});
test('empty or malformed push still displays a visible notification',async()=>{
 const f=fixture();let work;
 for(const data of [null,{json(){throw Error('invalid');}}]){f.listeners.push({data,waitUntil:p=>work=p});await work;}
 assert.equal(f.notifications.length,2);assert.equal(f.notifications[0].title,'TTT 알림');
});
test('notification links stay on this app and clicks focus existing windows',async()=>{
 const f=fixture();let work,focused=false,closed=false;
 f.listeners.push({data:{json:()=>({data:{url:'https://foreign.test/'}})},waitUntil:p=>work=p});await work;assert.equal(f.notifications[0].data.url,'/');
 f.listeners.notificationclick({notification:{data:{url:'https://foreign.test/'},close:()=>closed=true},waitUntil:p=>work=p});await work;
 assert.equal(f.opened[0],'https://example.test/');assert.ok(closed);
 f.self.clients.matchAll=async()=>[{url:'https://example.test/',focus:async()=>focused=true}];
 f.listeners.notificationclick({notification:{data:{url:'/'},close(){}},waitUntil:p=>work=p});await work;assert.ok(focused);assert.equal(f.opened.length,1);
});

test('health check distinguishes no receipt, received/displayed, and display failure without storing content',async()=>{
 const f=fixture();let work,health;
 const check=async()=>{f.listeners.message({data:{type:'TTT_PUSH_HEALTH'},ports:[{postMessage:value=>health=value}],waitUntil:p=>work=p});await work;return health;};
 assert.equal((await check()).receipt,null);
 f.listeners.push({data:{json:()=>({notification:{title:'private-title',body:'private-body'}})},waitUntil:p=>work=p});await work;
 health=await check();assert.ok(health.pushReady);assert.ok(health.receipt.receivedAt);assert.equal(health.receipt.displayed,true);
 assert.ok(!JSON.stringify(health).includes('private'));
 f.self.registration.showNotification=async()=>{throw Error('denied');};
 f.listeners.push({data:null,waitUntil:p=>work=p});await work;assert.equal((await check()).receipt.displayed,false);
});
