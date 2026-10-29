const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function fixture(){
 const listeners={},notifications=[],opened=[],receiptStore=new Map();
 const self={location:{origin:'https://example.test'},registration:{showNotification:async(title,options)=>notifications.push({title,...options})},clients:{matchAll:async()=>[],openWindow:async url=>opened.push(url)}};
 self.addEventListener=(name,listener)=>{const previous=listeners[name];listeners[name]=previous?event=>{previous(event);listener(event);}:listener;};
 const caches={open:async()=>({put:async(key,value)=>receiptStore.set(key,value),match:async key=>receiptStore.get(key)?.clone()})};
 vm.runInNewContext(fs.readFileSync('sw.js','utf8'),{self,URL,caches,Response});
 return {self,listeners,notifications,opened,receiptStore};
}
test('FCM Web Push shows a notification without Firestore access',async()=>{
 const f=fixture();let work;
 f.listeners.message({data:{type:'TTT_PUSH_SESSION',uid:'alice'},waitUntil:p=>work=p});await work;
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

test('logged-out or different-account pushes hide account-specific content',async()=>{
 const f=fixture();let work;
 const payload={notification:{title:'private-title',body:'private-body'},data:{receiverUid:'alice'}};
 f.listeners.push({data:{json:()=>payload},waitUntil:p=>work=p});await work;
 assert.ok(!JSON.stringify(f.notifications[0]).includes('private'));
 f.listeners.message({data:{type:'TTT_PUSH_SESSION',uid:'bob'},waitUntil:p=>work=p});await work;
 f.listeners.push({data:{json:()=>payload},waitUntil:p=>work=p});await work;
 assert.ok(!JSON.stringify(f.notifications[1]).includes('private'));
});

test('diagnostics records receipt and display success without message contents',async()=>{
 const f=fixture();let work,result;
 f.listeners.push({data:{json:()=>({notification:{title:'secret',body:'private'}})},waitUntil:p=>work=p});await work;
 f.listeners.message({data:{type:'TTT_PUSH_DIAGNOSTICS'},ports:[{postMessage:value=>result=value}],waitUntil:p=>work=p});await work;
 assert.equal(result.worker,'mf-v231');assert.equal(result.receipt.status,'shown');assert.ok(result.receipt.receivedAt>0);
 assert.ok(!JSON.stringify(result).includes('private'));assert.ok(!JSON.stringify(result).includes('secret'));
});
test('diagnostics preserves notification failure name',async()=>{
 const f=fixture();let work,result;
 f.self.registration.showNotification=async()=>{throw Object.assign(new Error('sensitive detail'),{name:'NotAllowedError'});};
 f.listeners.push({data:null,waitUntil:p=>work=p});await assert.rejects(work);
 f.listeners.message({data:{type:'TTT_PUSH_DIAGNOSTICS'},ports:[{postMessage:value=>result=value}],waitUntil:p=>work=p});await work;
 assert.equal(result.receipt.status,'failed');assert.equal(result.receipt.errorName,'NotAllowedError');assert.ok(!JSON.stringify(result).includes('sensitive'));
});

test('an explicit empty title stays empty for the signed-in recipient, while missing title uses fallback',async()=>{
 const f=fixture();let work;
 f.listeners.message({data:{type:'TTT_PUSH_SESSION',uid:'alice'},waitUntil:p=>work=p});await work;
 for(const notification of [{title:'',body:'운동 리마인더'},{body:'다른 알림'}]){
  f.listeners.push({data:{json:()=>({notification,data:{receiverUid:'alice'}})},waitUntil:p=>work=p});await work;
 }
 assert.equal(f.notifications[0].title,'');assert.equal(f.notifications[0].body,'운동 리마인더');
 assert.equal(f.notifications[1].title,'TTT 알림');
 f.listeners.message({data:{type:'TTT_PUSH_SESSION',uid:'bob'},waitUntil:p=>work=p});await work;
 f.listeners.push({data:{json:()=>({notification:{title:'',body:'private'},data:{receiverUid:'alice'}})},waitUntil:p=>work=p});await work;
 assert.equal(f.notifications[2].title,'TTT 알림');assert.ok(!f.notifications[2].body.includes('private'));
});
