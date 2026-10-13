const {test}=require('node:test');const assert=require('node:assert/strict');const {create}=require('../js/read-cache.js');
test('repeated navigation shares reads, reuses local edits and expires after five minutes',async()=>{
 let time=0,reads=0,release,local=['original'];const cache=create({now:()=>time});const read=()=>{reads++;return new Promise(r=>release=r);};
 const first=cache.run('a','list',read);const second=cache.run('a','list',read);assert.equal(first,second);await Promise.resolve();release(local);await first;
 local=['edited'];assert.deepEqual(await cache.run('a','list',read,{reuse:()=>local}),local);assert.equal(reads,1);
 time=300001;const next=cache.run('a','list',read);await Promise.resolve();release(['remote']);await next;assert.equal(reads,2);
});
test('accounts are isolated and failed requests do not make empty data fresh',async()=>{
 const cache=create();let reads=0;const read=async()=>++reads;
 assert.equal(await cache.run('a','records',read),1);assert.equal(await cache.run('b','records',read),2);
 await assert.rejects(cache.run('a','bad',async()=>{throw Error('offline');}));assert.equal(await cache.run('a','bad',read),3);
});
test('statistics count returned documents and distinguish local cache; do not contain data',()=>{
 const cache=create();cache.noteSnapshot({docs:[{id:'secret'},{id:'other'}],metadata:{fromCache:false}});cache.noteSnapshot({docs:[],metadata:{fromCache:false}});cache.noteSnapshot({exists:true,metadata:{fromCache:true}});
 assert.equal(cache.report().estimatedServerReads,3);assert.equal(cache.report().cacheDocuments,1);assert.equal(JSON.stringify(cache.report()).includes('secret'),false);
});
test('freshness survives restart only when the account still has its local cache',async()=>{
 const values=new Map();const storage={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};let time=1000,reads=0;
 const first=create({storage,now:()=>time});await first.run('a','records',async()=>++reads);
 const restarted=create({storage,now:()=>time});await restarted.run('a','records',async()=>++reads,{reuse:()=>undefined,hasLocal:()=>true});assert.equal(reads,1);
 await restarted.run('b','records',async()=>++reads,{hasLocal:()=>true});assert.equal(reads,2);
 const lost=create({storage,now:()=>time});await lost.run('a','records',async()=>++reads,{hasLocal:()=>false});assert.equal(reads,3);
 time=302000;const stale=create({storage,now:()=>time});await stale.run('a','records',async()=>++reads,{hasLocal:()=>true});assert.equal(reads,4);
});
test('history TTL persists for 24 hours while ordinary reads still expire at five minutes',async()=>{
 const values=new Map(),storage={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};let time=1000,reads=0;
 const options={ttlMs:86400000,hasLocal:()=>true,reuse:()=>false};
 await create({storage,now:()=>time}).run('alice','exerciseHistory:press',async()=>++reads,options);
 time+=3600000;
 const restarted=create({storage,now:()=>time});await restarted.run('alice','exerciseHistory:press',async()=>++reads,options);assert.equal(reads,1);
 time+=86400000;await restarted.run('alice','exerciseHistory:press',async()=>++reads,options);assert.equal(reads,2);
 await restarted.run('alice','exerciseHistory:press',async()=>++reads,{...options,hasLocal:()=>false});assert.equal(reads,3);
});
test('failed history persistence never creates a completion stamp and can retry',async()=>{
 const values=new Map(),storage={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};const cache=create({storage});
 await assert.rejects(cache.run('a','history',async()=>{throw Error('local quota');},{ttlMs:86400000}));
 assert.equal(values.size,0);await cache.run('a','history',async()=>true,{ttlMs:86400000});assert.equal(values.size,1);
});
