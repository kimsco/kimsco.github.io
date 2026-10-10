(function(root) {
  'use strict';
  const DAY = 86400000, KST = 9 * 3600000;
  const timestamp = value => typeof value === 'number' ? value : value?.toMillis?.() ||
    (Number.isFinite(value?.seconds) ? value.seconds * 1000 : 0);
  function koreanDay(ms) { return new Date(ms + KST).toISOString().slice(0,10); }
  function recordDay(row) {
    const ms = timestamp(row.createdAt) || timestamp(row.completedAt) || row.firstAt || 0;
    if (ms) return koreanDay(ms);
    const match = /^(\d{2})\.(\d{2})\.(\d{2})$/.exec(row.date || '');
    return match ? `20${match[1]}-${match[2]}-${match[3]}` : null;
  }
  function normalize({records = {}, accessories = {}, bodyweightRoutines = []}) {
    const rows = [], seen = new Set();
    const add = (row, exercise, kind, fallback) => {
      const id = `${kind}:${row.firestoreId || row.id || row.localId || fallback}`;
      if (seen.has(id)) return;
      seen.add(id);
      const sets = Math.max(1, Math.floor(Number(row.sets) || 1));
      const weight = Math.max(0, Number(row.weight) || 0), reps = Math.max(0, Number(row.reps) || 0);
      rows.push({...row, id, exercise, sets, weight, reps, day:recordDay(row),
        isWarmup:row.isWarmup === true || row.warmup === true || row.setType === 'warmup',
        at:timestamp(row.createdAt) || timestamp(row.completedAt) || row.firstAt || 0});
    };
    for (const [lift,list] of Object.entries(records)) (list || []).forEach((r,i)=>add(r,lift,'lift',`${lift}:${i}`));
    for (const [name,list] of Object.entries(accessories)) (list || []).forEach((r,i)=>add(r,r.exercise || name,'accessory',`${name}:${i}`));
    for (const routine of bodyweightRoutines) {
      (routine.exercises || []).forEach((ex,i)=>add({id:`${routine.id}:${i}`,date:routine.date,
        completedAt:routine.completedAt, sessionId:routine.sessionId, weight:0, reps:ex.reps,
        sets:routine.totalSets, isWarmup:routine.isWarmup},ex.kr || ex.en,'bodyweight',`${routine.id}:${i}`));
    }
    return rows;
  }
  function summarize(rows) {
    const work = rows.filter(r=>!r.isWarmup);
    return {exercises:new Set(work.map(r=>r.exercise)).size, sets:work.reduce((n,r)=>n+r.sets,0),
      warmupSets:rows.filter(r=>r.isWarmup).reduce((n,r)=>n+r.sets,0),
      volume:Math.round(work.reduce((n,r)=>n+r.weight*r.reps*r.sets,0)*10)/10,
      bodyweightSets:work.filter(r=>r.weight===0).reduce((n,r)=>n+r.sets,0),
      days:new Set(work.map(r=>r.day).filter(Boolean)).size};
  }
  function weekRange(now = Date.now()) {
    const day = koreanDay(now), date = new Date(day+'T00:00:00Z');
    const start = date.getTime() - date.getUTCDay() * DAY;
    const iso = ms => new Date(ms).toISOString().slice(0,10);
    return {start:iso(start),end:iso(start+7*DAY),previousStart:iso(start-7*DAY)};
  }
  function weekly(rows, now) {
    const range = weekRange(now);
    const current = summarize(rows.filter(r=>r.day>=range.start && r.day<range.end));
    const previous = summarize(rows.filter(r=>r.day>=range.previousStart && r.day<range.start));
    return {range,current,previous};
  }
  function comparison(current, previous, unit) {
    if (!current && !previous) return '지난주와 이번 주 기록이 없어요';
    if (!previous) return `이번 주 ${current.toLocaleString()}${unit} · 지난주 기록 없음`;
    const diff = Math.round((current-previous)*10)/10;
    if (!diff) return '지난주와 같아요';
    return `지난주보다 ${Math.abs(diff).toLocaleString()}${unit} ${diff>0?'증가':'감소'}`;
  }
  // Per-exercise records: a higher external weight is a PR; at equal weight compare reps.
  // Bodyweight PR compares reps. Warmups and other sets in this session are excluded from baseline.
  function personalRecords(sessionRows, allRows) {
    const ids = new Set(sessionRows.map(r=>r.id));
    const sessionStart = Math.min(...sessionRows.map(r=>r.at || Infinity));
    const results = [];
    for (const exercise of new Set(sessionRows.filter(r=>!r.isWarmup).map(r=>r.exercise))) {
      const rows = sessionRows.filter(r=>!r.isWarmup && r.exercise===exercise);
      const score = rows => rows.reduce((best,r)=>!best || r.weight>best.weight || (r.weight===best.weight && r.reps>best.reps) ? r : best,null);
      const best = score(rows), previous = score(allRows.filter(r=>!r.isWarmup && r.exercise===exercise && !ids.has(r.id) && (!r.at || r.at<sessionStart)));
      if (!previous) results.push({exercise,weight:best.weight,reps:best.reps,first:true});
      else if (best.weight>previous.weight || (best.weight===previous.weight && best.reps>previous.reps)) results.push({exercise,weight:best.weight,reps:best.reps,first:false});
    }
    return results;
  }
  function createSession({storage, key, now = Date.now, id = () => root.crypto?.randomUUID?.() || `${Date.now()}_${Math.random()}`}) {
    const read = () => { try { return JSON.parse(storage.getItem(key) || '{"active":null,"last":null}'); } catch (_) { return {active:null,last:null}; }};
    const write = data => storage.setItem(key,JSON.stringify(data));
    return {
      state:read,
      prepare() {
        const data=read();
        if (!data.active) { data.active={id:id(),startedAt:now(),endedAt:null,pending:true};write(data); }
        return data.active;
      },
      accept(session, at = now()) {
        const data=read();
        const active = data.active?.id === session.id ? data.active : session;
        data.active={...active,startedAt:active.pending ? at : active.startedAt,pending:false};write(data);
      },
      recover(rows) {
        const data=read();
        if (data.active) {
          if (data.active.pending && rows.some(r=>r.sessionId===data.active.id)) {
            const at = Math.min(...rows.filter(r=>r.sessionId===data.active.id).map(r=>r.at || data.active.startedAt));
            data.active={...data.active,pending:false,startedAt:at};write(data);
          }
          return data.active;
        }
        const orphan = rows.filter(r=>r.sessionId && (!data.last || r.sessionId!==data.last.id) && (!data.last || r.at>data.last.endedAt)).sort((a,b)=>a.at-b.at);
        if (!orphan.length) return null;
        const session={id:orphan.at(-1).sessionId,startedAt:orphan.find(r=>r.sessionId===orphan.at(-1).sessionId).at,endedAt:null};
        data.active=session;write(data);return session;
      },
      finish(rows, allRows, {historyComplete = false} = {}) {
        const data=read();if (!data.active || data.active.pending) return null;
        const sessionRows=rows.filter(r=>r.sessionId===data.active.id);
        data.last={...data.active,endedAt:now(),summary:summarize(sessionRows),
          personalRecords:personalRecords(sessionRows,allRows),historyComplete};
        data.active=null;write(data);return data.last;
      }
    };
  }
  const api={timestamp,koreanDay,recordDay,normalize,summarize,weekRange,weekly,comparison,personalRecords,createSession};
  if (typeof module !== 'undefined') module.exports=api;
  root.MFWorkout=api;
})(typeof window==='undefined'?globalThis:window);
