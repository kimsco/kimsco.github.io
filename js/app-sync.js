(function(root) {
  'use strict';
  function install({db, auth, firebase, storage, onStatus}) {
    const account = root.MFSync.createAccountStorage(storage);
    const clean = value => {
      if (value instanceof firebase.firestore.FieldValue) return Date.now();
      if (value?.toMillis) return value.toMillis();
      if (Array.isArray(value)) return value.map(clean);
      if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k,clean(v)]));
      return value;
    };
    function withTimestamps(collection, data) {
      const result = {...data};
      if (['records','accessoryRecords'].includes(collection) && Number.isFinite(result.createdAt)) {
        result.createdAt = firebase.firestore.Timestamp.fromMillis(result.createdAt);
      }
      return result;
    }
    const lock = (name, fn) => navigator.locks ? navigator.locks.request(name, fn) : Promise.resolve().then(fn);
    const stateLock = (uid,fn) => lock(`mf-outbox-state:${uid}`, fn);
    const outbox = root.MFSync.createOutbox({storage, currentUid: () => auth.currentUser?.uid,
      lockState:stateLock, lead:(uid,fn) => lock(`mf-outbox-send:${uid}`, fn),
      online: () => navigator.onLine,
      onChange: (uid,state,error) => { if (uid === auth.currentUser?.uid) onStatus(Object.keys(state.ops).length,error); },
      send: async (uid, op) => {
        if (auth.currentUser?.uid !== uid) throw new Error('Account changed');
        const collection = db.collection('users').doc(uid).collection(op.collection);
        if (op.matchExercise) {
          while (true) {
            if (auth.currentUser?.uid !== uid) throw new Error('Account changed');
            const snap = await collection.where('exercise','==',op.matchExercise).limit(400).get({source:'server'});
            if (!snap.docs.length) return;
            const batch = db.batch();
            snap.docs.forEach(doc => op.data === null ? batch.delete(doc.ref) : batch.update(doc.ref,op.data));
            await batch.commit();
          }
        }
        const ref = collection.doc(op.id);
        if (op.data === null) await ref.delete();
        else await ref.set(withTimestamps(op.collection, op.data), {merge: op.merge});
      }});
    const retry = () => { const uid = auth.currentUser?.uid; if (uid) void outbox.flush(uid); };
    root.addEventListener('online', retry);
    root.addEventListener('pageshow', retry);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) retry(); });
    setInterval(retry, 15000);
    // IndexedDB persistence is paused on sign-out so no new writes dispatch as another account.
    function write(uid, collection, id, data, options) {
      return stateLock(uid, () => outbox.enqueue(uid, collection, id, data === null ? null : clean(data), options))
        .catch(error => { onStatus(null,error); throw error; });
    }
    function snapshot(snap, collection, uid, id) {
      const doc = (d) => ({id:d.id, exists:true, data:() => withTimestamps(collection,d.data)});
      if (id !== undefined) {
        const items = outbox.overlay(uid, collection, snap.exists ? [{id, data:snap.data()}] : []);
        return items.find(d => d.id === id) ? doc(items.find(d => d.id === id)) : {id,exists:false};
      }
      const items = outbox.overlay(uid, collection, snap.docs.map(d => ({id:d.id,data:d.data()}))).map(doc);
      return {docs:items, empty:!items.length, forEach(fn) {items.forEach(fn);}};
    }
    return {account, outbox, write, snapshot, retry};
  }
  root.MFAppSync = {install};
})(window);
