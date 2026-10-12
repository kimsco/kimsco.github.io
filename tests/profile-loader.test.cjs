const {test}=require('node:test');const assert=require('node:assert/strict');
const {create}=require('../js/profile-loader.js');
test('profile retry recovers a failed first read and concurrent calls share it',async()=>{
 let calls=0,applied=[],states=[];const loader=create({currentOwner:()=> 'a',read:async()=>{if(++calls===1)throw Error('unavailable');return 'profile';},apply:x=>applied.push(x),onState:x=>states.push(x),retryMs:1});
 const first=loader.load('a');assert.equal(loader.load('a'),first);assert.equal(await first,true);
 assert.equal(calls,2);assert.deepEqual(applied,['profile']);assert.deepEqual(states,['pending','retry','ready']);
});
test('stalled reads terminate, cannot apply late data, and can be retried',async()=>{
 let resolve,applyCount=0;const loader=create({currentOwner:()=> 'a',read:()=>new Promise(r=>resolve=r),apply:()=>applyCount++,timeoutMs:5,attempts:1});
 assert.equal(await loader.load('a'),false);resolve('late');await new Promise(r=>setTimeout(r,1));assert.equal(applyCount,0);
 const retry=loader.load('a');await Promise.resolve();resolve('success');assert.equal(await retry,true);assert.equal(applyCount,1);
});
test('a switched account cannot receive an old profile',async()=>{
 let owner='a',resolve,applyCount=0;const loader=create({currentOwner:()=>owner,read:()=>new Promise(r=>resolve=r),apply:()=>applyCount++});
 const task=loader.load('a');await Promise.resolve();owner='b';resolve('a data');assert.equal(await task,false);assert.equal(applyCount,0);
});
test('offline attempts do not issue server reads or report success',async()=>{
 let reads=0;const states=[];const loader=create({currentOwner:()=> 'a',online:()=>false,read:()=>reads++,apply:()=>{},onState:s=>states.push(s)});
 assert.equal(await loader.load('a'),false);assert.equal(reads,0);assert.deepEqual(states,['pending','error']);
});
