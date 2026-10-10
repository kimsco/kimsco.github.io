const {test}=require('node:test');const assert=require('node:assert/strict');
const M=require('../js/workout-summary.js');
class Storage {constructor(){this.d=new Map();}getItem(k){return this.d.get(k)||null;}setItem(k,v){this.d.set(k,v);}}
const row=(id,exercise,weight,reps,at,extra={})=>({id,exercise,weight,reps,sets:1,at,createdAt:at,day:M.koreanDay(at),isWarmup:false,...extra});
test('Korean Sunday boundary is independent of execution timezone',()=>{
 const saturday=Date.parse('2026-10-10T14:59:59Z'),sunday=Date.parse('2026-10-10T15:00:00Z');
 assert.equal(M.koreanDay(saturday),'2026-10-10');assert.equal(M.koreanDay(sunday),'2026-10-11');
 assert.deepEqual(M.weekRange(sunday),{start:'2026-10-11',end:'2026-10-18',previousStart:'2026-10-04'});
 const w=M.weekly([row('a','bench',80,5,saturday),row('b','bench',90,3,sunday)],sunday);
 assert.equal(w.previous.volume,400);assert.equal(w.current.volume,270);assert.equal(w.current.days,1);
});
test('volume and work sets exclude warmups; bodyweight contributes sets and exercises only',()=>{
 const now=Date.parse('2026-10-11T01:00Z');const rows=[row('a','bench',80,5,now,{sets:2}),row('b','bench',20,10,now,{isWarmup:true}),row('c','pushup',0,15,now)];
 assert.deepEqual(M.summarize(rows),{exercises:2,sets:3,warmupSets:1,volume:800,bodyweightSets:1,days:1});
});
test('legacy date fallback and serialized Firestore timestamps are supported',()=>{
 assert.equal(M.recordDay({date:'26.10.11'}),'2026-10-11');assert.equal(M.recordDay({createdAt:{seconds:Date.parse('2026-10-10T15:00Z')/1000},date:'26.10.10'}),'2026-10-11');
 assert.equal(M.recordDay({date:'bad'}),null);
});
test('bodyweight routine rounds expand per exercise without generating duplicate stored records',()=>{
 const rows=M.normalize({bodyweightRoutines:[{id:'routine',date:'26.10.11',totalSets:3,totalReps:60,exercises:[{kr:'pushup',reps:10},{kr:'pullup',reps:10}]}]});
 assert.equal(rows.length,2);assert.equal(M.summarize(rows).sets,6);assert.equal(M.summarize(rows).volume,0);
});
test('normalization deduplicates stable IDs and retains warmup flags',()=>{
 const r={firestoreId:'same',date:'26.10.11',weight:60,reps:5};const rows=M.normalize({records:{bench:[r,{...r}]},accessories:{curl:[{id:'x',date:'26.10.11',setType:'warmup',weight:10,reps:10}]}});
 assert.equal(rows.length,2);assert.equal(M.summarize(rows).sets,1);assert.equal(M.summarize(rows).warmupSets,1);
});
test('zero comparison displays naturally and never divides by zero',()=>{
 assert.equal(M.comparison(0,0,'세트'),'지난주와 이번 주 기록이 없어요');assert.match(M.comparison(5,0,'세트'),/지난주 기록 없음/);assert.match(M.comparison(0,5,'세트'),/5세트 감소/);assert.equal(M.comparison(5,5,'세트'),'지난주와 같아요');
});
test('PR compares historical weight then reps, ignores warmups, and handles bodyweight',()=>{
 const at=Date.parse('2026-10-11T01:00Z');const previous=[row('old','bench',80,5,at-100000),row('old-push','pushup',0,15,at-100000)];
 const current=[row('now','bench',80,6,at),row('warmup','bench',100,1,at,{isWarmup:true}),row('push','pushup',0,20,at)];
 const prs=M.personalRecords(current,[...previous,...current]);assert.equal(prs.length,2);assert.equal(prs[0].weight,80);assert.equal(prs[0].reps,6);assert.equal(prs[1].weight,0);assert.ok(prs.every(p=>!p.first));
});
test('first saved set starts session, reload restores it, finish is idempotent, next set starts new session',()=>{
 const storage=new Storage();let now=1000,count=0;const opts={storage,key:'session',now:()=>now,id:()=>String(++count)};
 const first=M.createSession(opts);const initial=first.prepare();assert.equal(first.state().active.pending,true);first.accept(initial,now);
 now=2000;const reloaded=M.createSession(opts);assert.equal(reloaded.prepare().id,initial.id);const r=row('a','bench',60,5,now,{sessionId:initial.id});
 const last=reloaded.finish([r],[r]);assert.equal(last.summary.volume,300);assert.equal(reloaded.state().active,null);assert.equal(reloaded.finish([r],[r]),null);
 assert.equal(reloaded.recover([r]),null);now=3000;assert.notEqual(reloaded.prepare().id,initial.id);
});
test('restart recovers staged session metadata and deleted sets do not contribute',()=>{
 const storage=new Storage();const session=M.createSession({storage,key:'session',now:()=>1000,id:()=> 's'});session.prepare();
 const a=row('a','bench',60,5,1000,{sessionId:'s'}),b=row('b','curl',10,10,2000,{sessionId:'s'});
 session.recover([a,b]);assert.equal(session.state().active.pending,false);const last=session.finish([b],[a,b]);assert.equal(last.summary.sets,1);assert.equal(last.summary.exercises,1);assert.equal(last.summary.volume,100);
});
test('weekly totals use two full calendar weeks and ignore future/outside data',()=>{
 const at=Date.parse('2026-10-14T01:00Z');const rows=[row('this','bench',80,5,at),row('prev','bench',70,5,at-7*86400000),row('older','bench',100,5,at-14*86400000),row('next','bench',200,5,at+7*86400000)];const w=M.weekly(rows,at);assert.equal(w.current.sets,1);assert.equal(w.previous.sets,1);assert.equal(w.current.volume,400);assert.equal(w.previous.volume,350);
});
