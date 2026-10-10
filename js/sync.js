/* Durable, account-scoped writes. Firebase persistence remains a second safety net. */
(function(root) {
  'use strict';
  const PRIVATE_COLLECTIONS = Object.freeze(['records', 'accessoryRecords', 'calendar', 'threeRM',
    'accessories', 'profile', 'foodTemplates', 'meals', 'myRoutineTemplates', 'meta', 'diets']);
  const PUBLIC_KEYS = new Set(['mf_dex_folders_v1', 'mf_dex_posts_v1', 'mf_dex_pending_ids_v1']);
  function createAccountStorage(storage) {
    let owner = storage.getItem('mf_data_owner_v2') || 'guest';
    const key = name => PUBLIC_KEYS.has(name) ? name : `mf_account_v2:${owner}:${name}`;
    return {
      get owner() { return owner; }, key,
      select(uid, email) {
        const next = uid || 'guest';
        // Legacy caches have no uid. Claim them only for a guest or the cached matching login.
        const matchingLegacy = uid ? storage.getItem('mf_cached_email') === email : storage.getItem('mf_was_logged_in') !== '1';
        let migrated = false;
        if (!storage.getItem('mf_legacy_migrated_v2') && matchingLegacy) {
          const names = Array.from({length: storage.length}, (_, i) => storage.key(i));
          for (const name of names) {
            if (!/^mf_(threeRM|records|calendar|acc_|user_spec|food_templates|meals|water|weight|my_routine|exercise_ref|bodyweight|core_seeded|arm_)/.test(name)) continue;
            const target = `mf_account_v2:${next}:${name}`;
            if (storage.getItem(target) === null) { storage.setItem(target, storage.getItem(name)); migrated = true; }
            storage.removeItem(name);
          }
          storage.setItem('mf_legacy_migrated_v2', '1');
        }
        const changed = next !== owner;
        owner = next;
        storage.setItem('mf_data_owner_v2', owner);
        return changed || migrated;
      },
      clear(uid) {
        const prefix = `mf_account_v2:${uid}:`;
        const names = Array.from({length: storage.length}, (_, i) => storage.key(i));
        names.filter(name => name.startsWith(prefix) || name === `mf_full_sync_at_${uid}`).forEach(name => storage.removeItem(name));
      }
    };
  }
  function createOutbox({storage, send, currentUid, onChange = () => {}, online = () => true,
    lockState = (_, fn) => fn(), lead = (_, fn) => fn()}) {
    const key = uid => `mf_account_v2:${uid}:outbox`;
    const read = uid => JSON.parse(storage.getItem(key(uid)) || '{"ops":{},"deleted":{}}');
    const write = (uid, state) => { storage.setItem(key(uid), JSON.stringify(state)); onChange(uid, state); };
    const running = new Map();
    const blocked = new Set();
    const freshId = () => root.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2)}`;
    function enqueue(uid, collection, id, data, options) {
      if (!uid || !PRIVATE_COLLECTIONS.includes(collection) || !id || String(id).includes('/')) throw new Error('Invalid private write');
      if (blocked.has(uid) || storage.getItem(`mf_account_v2:${uid}:deleting`) === '1') throw new Error('회원 탈퇴 진행 중에는 저장할 수 없습니다.');
      const state = read(uid), path = `${collection}/${id}`;
      state.deletedExercises ||= {};
      if (options?.matchExercise) {
        if (collection !== 'accessoryRecords') throw new Error('Invalid exercise operation');
        for (const [pendingPath,pending] of Object.entries(state.ops)) {
          if (pending.collection !== collection || pending.data?.exercise !== options.matchExercise) continue;
          if (data === null) { delete state.ops[pendingPath]; state.deleted[pendingPath] = true; }
          else { pending.data.exercise = data.exercise; pending.revision = freshId(); }
        }
        if (data === null) state.deletedExercises[options.matchExercise] = true;
      } else if (collection === 'accessoryRecords' && data?.exercise) {
        delete state.deletedExercises[data.exercise];
      }
      const previous = state.ops[path];
      const combine = data !== null && options?.merge && previous?.data;
      const op = {collection, id, data: combine ? {...previous.data, ...data} : data ?? null,
        merge: combine ? previous.merge : !!options?.merge, revision: freshId(), matchExercise:options?.matchExercise};
      state.ops[path] = op;
      if (data === null) state.deleted[path] = true; else delete state.deleted[path];
      write(uid, state); // Never report a saved record if durable storage failed.
      void flush(uid);
      return {id, pending: true};
    }
    async function flush(uid = currentUid()) {
      if (!uid || running.has(uid) || blocked.has(uid) || storage.getItem(`mf_account_v2:${uid}:deleting`) === '1' || currentUid() !== uid || !online()) return;
      const task = lead(uid, async () => {
        while (currentUid() === uid && online() && !blocked.has(uid)) {
          const state = read(uid), op = Object.values(state.ops)[0];
          if (!op) break;
          try { await send(uid, op); }
          catch (error) { onChange(uid, read(uid), error); break; }
          await lockState(uid, () => {
            const latest = read(uid), path = `${op.collection}/${op.id}`;
            if (latest.ops[path]?.revision === op.revision) {
              delete latest.ops[path];
              write(uid, latest);
            }
          });
        }
      });
      running.set(uid, task);
      try { await task; } finally { running.delete(uid); }
    }
    function overlay(uid, collection, documents) {
      if (!uid) return documents;
      const state = read(uid), result = new Map(documents.filter(d => collection !== 'accessoryRecords' || !state.deletedExercises?.[d.data.exercise]).map(d => [d.id, d]));
      for (const path of Object.keys(state.deleted)) {
        if (path.startsWith(collection + '/')) result.delete(path.slice(collection.length + 1));
      }
      for (const op of Object.values(state.ops)) {
        if (op.collection !== collection) continue;
        if (op.matchExercise) {
          if (op.data) for (const [id,doc] of result) if (doc.data.exercise === op.matchExercise) result.set(id,{id,data:{...doc.data,...op.data}});
          continue;
        }
        if (op.data === null) result.delete(op.id);
        else result.set(op.id, {id: op.id, data: op.merge ? {...result.get(op.id)?.data, ...op.data} : op.data});
      }
      return Array.from(result.values());
    }
    return {enqueue, flush, overlay, read, freshId,
      async freeze(uid) { blocked.add(uid); storage.setItem(`mf_account_v2:${uid}:deleting`, '1'); await running.get(uid); },
      isDeleting(uid) { return storage.getItem(`mf_account_v2:${uid}:deleting`) === '1'; },
      clear(uid) { storage.removeItem(key(uid)); },
      resume(uid) { blocked.delete(uid); storage.removeItem(`mf_account_v2:${uid}:deleting`); void flush(uid); }};
  }
  // All currently used private subcollections are flat. Explicitly enumerate them;
  // deleting users/{uid} never cascades. Fetch server pages, never trust an offline cache.
  async function deletePrivateData(db, uid, checkIdentity = () => {}) {
    if (!uid || String(uid).includes('/')) throw new Error('Invalid uid');
    const user = db.collection('users').doc(uid);
    for (const name of PRIVATE_COLLECTIONS) {
      while (true) {
        checkIdentity();
        const snap = await user.collection(name).limit(400).get({source: 'server'});
        if (snap.empty || !snap.docs.length) break;
        const batch = db.batch();
        snap.docs.forEach(doc => batch.delete(doc.ref));
        await batch.commit();
      }
    }
    checkIdentity();
    await user.delete();
  }
  const api = {PRIVATE_COLLECTIONS, createAccountStorage, createOutbox, deletePrivateData};
  if (typeof module !== 'undefined') module.exports = api;
  root.MFSync = api;
})(typeof window === 'undefined' ? globalThis : window);
