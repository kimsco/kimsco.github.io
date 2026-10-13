const {test}=require('node:test');const assert=require('node:assert/strict');const {create}=require('../js/history-pages.js');
function fixture(){let time=1000,uid='a',local=true,fail=false,full=false;const saved=new Map(),reads=[];const docs=Array.from({length:123},(_,i)=>({id:String(1000-i),data:()=>({date:'20.01.01'})}));
 const options={storage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},currentUid:()=>uid,hasLocal:()=>local,fullFresh:()=>full,now:()=>time,
 query:async(u,k,n,s)=>{reads.push(s);const start=s.cursor?docs.findIndex(d=>d.id===s.cursor.id)+1:0;return {docs:docs.slice(start,start+s.limit)};},apply:async()=>{if(fail)throw Error('quota');return true;}};
 return {options,reads,saved,setTime:v=>time=v,setUid:v=>uid=v,setLocal:v=>local=v,setFail:v=>fail=v,setFull:v=>full=v};}
test('50-record pages resume after restart without duplicates, exhaust and remain account scoped',async()=>{
 const f=fixture();await create(f.options).next('lift','bench','26.01.01');await create(f.options).next('lift','bench','26.01.02');const service=create(f.options);await service.next('lift','bench','26.01.03');assert.equal(service.done('lift','bench'),true);assert.equal(f.reads.length,3);assert.equal(f.reads[1].before,'26.01.01');assert.equal(f.reads[1].cursor.id,'951');await service.next('lift','bench','26.01.03');assert.equal(f.reads.length,3);
 f.setUid('b');await service.next('lift','bench','26.01.03');assert.equal(f.reads[3].cursor,null);
});
test('local save failure does not advance cursor; retry requests same page',async()=>{
 const f=fixture(),s=create(f.options);f.setFail(true);await assert.rejects(s.next('accessory','press','26.01.01'));assert.equal(f.saved.size,0);f.setFail(false);await s.next('accessory','press','26.01.01');assert.equal(f.reads[1].cursor,null);
});
test('24h expiry, missing cache and full-history freshness are respected',async()=>{
 const f=fixture(),s=create(f.options);await s.next('lift','bench','26.01.01');f.setTime(86402000);await s.next('lift','bench','26.01.02');assert.equal(f.reads[1].cursor,null);f.setLocal(false);await s.next('lift','bench','26.01.02');assert.equal(f.reads[2].cursor,null);f.setFull(true);await s.next('lift','bench','26.01.02');assert.equal(f.reads.length,3);
});
test('concurrent page requests share one query; account switch cannot persist another account page',async()=>{
 const f=fixture();let release,applied=0;f.options.query=()=>new Promise(r=>release=r);f.options.apply=async()=>{applied++;};const s=create(f.options);
 const one=s.next('lift','bench','26.01.01'),two=s.next('lift','bench','26.01.01');assert.equal(one,two);
 f.setUid('b');release({docs:[]});await assert.rejects(one,/Account changed/);assert.equal(applied,0);assert.equal(f.saved.size,0);
});
test('index or network errors do not advance a cursor or trigger an unbounded fallback',async()=>{
 const f=fixture();let queries=0;f.options.query=async()=>{queries++;throw Error('failed-precondition: index required');};const s=create(f.options);
 await assert.rejects(s.next('lift','bench','26.01.01'),/index required/);assert.equal(queries,1);assert.equal(f.saved.size,0);assert.equal(s.done('lift','bench'),false);
});
