const {test}=require('node:test');const assert=require('node:assert/strict');const {create}=require('../js/history-pages.js');
function fixture(){let time=1000,uid='a',local=true,fail=false,full=false;const saved=new Map(),reads=[],applied=[];const docs=[];
 for(let day=9;day>=1;day--)for(let i=0;i<(day===9?123:day);i++)docs.push({id:String(1000-i).padStart(4,'0'),data:()=>({date:'20.01.0'+day})});
 const options={storage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},currentUid:()=>uid,hasLocal:()=>local,fullFresh:()=>full,now:()=>time,
 query:async(u,k,n,s)=>{reads.push(s);let rows=docs.filter(d=>!s.date || d.data().date===s.date);if(s.cursor)rows=rows.filter(d=>d.data().date<s.cursor.date || d.data().date===s.cursor.date && d.id<s.cursor.id);return {docs:rows.slice(0,s.limit)};},apply:async(u,k,n,s)=>{if(fail)throw Error('quota');applied.push(s.docs);return true;}};
 return {options,reads,saved,applied,setTime:v=>time=v,setUid:v=>uid=v,setLocal:v=>local=v,setFail:v=>fail=v,setFull:v=>full=v};}
test('pages contain exactly four complete workout dates, resume and do not read a fifth date',async()=>{
 const f=fixture();await create(f.options).next('lift','bench','26.01.01');assert.equal(new Set(f.applied[0].map(d=>d.data().date)).size,4);assert.equal(f.applied[0].length,144);assert.ok(f.applied[0].every(d=>d.data().date>='20.01.06'));
 await create(f.options).next('lift','bench','26.01.02');assert.equal(new Set(f.applied[1].map(d=>d.data().date)).size,4);assert.ok(f.applied[1].every(d=>d.data().date<'20.01.06'));
 const s=create(f.options);await s.next('lift','bench','26.01.03');assert.equal(s.done('lift','bench'),true);const calls=f.reads.length;await s.next('lift','bench','26.01.03');assert.equal(f.reads.length,calls);
 f.setUid('b');await s.next('lift','bench','26.01.03');assert.equal(f.reads[calls].cursor,null);
});
test('local save failure does not advance cursor; retry receives same four dates',async()=>{
 const f=fixture(),s=create(f.options);f.setFail(true);await assert.rejects(s.next('accessory','press','26.01.01'));assert.equal(f.saved.size,0);const count=f.reads.length;f.setFail(false);await s.next('accessory','press','26.01.01');assert.equal(f.reads[count].cursor,null);
});
test('history coverage survives age; missing cache and full-history completion are respected',async()=>{
 const f=fixture(),s=create(f.options);await s.next('lift','bench','26.01.01');let count=f.reads.length;f.setTime(86402000);await s.next('lift','bench','26.01.02');assert.notEqual(f.reads[count].cursor,null);count=f.reads.length;f.setLocal(false);await s.next('lift','bench','26.01.02');assert.equal(f.reads[count].cursor,null);count=f.reads.length;f.setFull(true);await s.next('lift','bench','26.01.02');assert.equal(f.reads.length,count);
});
test('concurrent page requests share one query; account switch cannot persist another account page',async()=>{
 const f=fixture();let release,applied=0;f.options.query=()=>new Promise(r=>release=r);f.options.apply=async()=>{applied++;};const s=create(f.options);
 const one=s.next('lift','bench','26.01.01'),two=s.next('lift','bench','26.01.01');assert.equal(one,two);f.setUid('b');release({docs:[]});await assert.rejects(one,/Account changed/);assert.equal(applied,0);assert.equal(f.saved.size,0);
});
test('index or network errors do not advance cursor or trigger full-history fallback',async()=>{
 const f=fixture();let queries=0;f.options.query=async()=>{queries++;throw Error('index required');};const s=create(f.options);await assert.rejects(s.next('lift','bench','26.01.01'));assert.equal(queries,1);assert.equal(f.saved.size,0);
});
