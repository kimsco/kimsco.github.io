import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createSender, firestoreStore} from '../notification-server/sender.mjs';

function fixture(initial = {}) {
  const docs = new Map(Object.entries(structuredClone(initial))), reads = [], sends = [];
  let transaction = Promise.resolve();
  function ref(path) {
    return {path, collection: name => collection(path + '/' + name),
      get: async () => snapshot(path),
      create: async value => {if (docs.has(path)) throw Object.assign(Error('exists'), {code: 6}); docs.set(path, structuredClone(value));},
      update: async value => {assert.ok(docs.has(path)); docs.set(path, {...docs.get(path), ...structuredClone(value)});}};
  }
  function snapshot(path) {
    reads.push(path);
    return {exists: docs.has(path), ref: ref(path), data: () => structuredClone(docs.get(path))};
  }
  function query(matches, filters = [], after = '', limit = 100) {
    return {where: (field, op, value) => {assert.equal(op, '=='); return query(matches, [...filters, [field, value]], after, limit);},
      orderBy: () => query(matches, filters, after, limit), limit: value => query(matches, filters, after, value),
      startAfter: cursor => query(matches, filters, cursor.ref.path, limit),
      get: async () => {
        const paths = [...docs.keys()].sort().filter(path => path > after && matches(path) && filters.every(([field, value]) => docs.get(path)[field] === value)).slice(0, limit);
        return {empty: !paths.length, size: paths.length, docs: paths.map(snapshot)};
      }};
  }
  function collection(path) {return {...query(candidate => candidate.startsWith(path + '/') && candidate.split('/').length === path.split('/').length + 1), doc: id => ref(path + '/' + id)};}
  const db = {doc: ref, collection,
    collectionGroup: name => query(path => path.split('/').at(-2) === name),
    runTransaction: fn => {
      const result = transaction.catch(() => {}).then(async () => {
        const writes = [], tx = {get: async r => snapshot(r.path),
          create: (r, value) => {assert.ok(!docs.has(r.path)); writes.push(() => docs.set(r.path, structuredClone(value)));},
          update: (r, value) => {assert.ok(docs.has(r.path)); writes.push(() => docs.set(r.path, {...docs.get(r.path), ...structuredClone(value)}));},
          delete: r => writes.push(() => docs.delete(r.path))};
        const value = await fn(tx); for (const write of writes) write(); return value;
      });
      transaction = result; return result;
    }};
  const store = firestoreStore(db, () => '__name__');
  const send = async message => {sends.push(structuredClone(message)); return 'accepted-id';};
  const sender = createSender({store, send, now: () => '2026-10-27T12:00:00Z'});
  return {docs, reads, sends, store, send, sender};
}
const ios = token => ({token, platform: 'ios', enabled: true});
const testInput = {runId: '101', title: 'Test', body: '기기 테스트 중입니다.', testUid: 'owner'};
const approve = {testRunId: '101', runId: '102', approval: 'SEND', testUid: 'owner'};

test('test sends only to configured owner iOS devices using registered tokens', async () => {
  const f = fixture({'users/owner/pushDevices/iphone': ios('owner-current'), 'users/other/pushDevices/iphone': ios('other'),
    'users/owner/pushDevices/android': {token: 'android', platform: 'android', enabled: true},
    'users/owner/pushDevices/disabled': {...ios('disabled'), enabled: false}});
  const result = await f.sender.test(testInput);
  assert.equal(result.accepted, 1); assert.deepEqual(f.sends.map(m => m.token), ['owner-current']);
  assert.equal(f.sends[0].data.receiverUid, 'owner'); assert.equal(f.sends[0].webpush.headers.Urgency, 'high');
  assert.equal(f.docs.get('pushCampaigns/test-101').state, 'awaiting_approval');
  assert.ok(!f.reads.some(path => path.includes('/records/') || path.startsWith('users/other/')));
  assert.ok(!JSON.stringify([...f.docs].filter(([path]) => path.startsWith('pushCampaigns/'))).includes('owner-current'));
});
test('test without an eligible iPhone fails and cannot authorize broadcast', async () => {
  const f = fixture(); await assert.rejects(f.sender.test(testInput), /성공한 아이폰/);
  await assert.rejects(f.sender.broadcast(approve)); assert.equal(f.sends.length, 0);
});
test('broadcast requires explicit approval of a successful test for the same account', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('owner')});
  await assert.rejects(f.sender.broadcast(approve));
  await f.sender.test(testInput);
  await assert.rejects(f.sender.broadcast({...approve, approval: ''}), /SEND/);
  await assert.rejects(f.sender.broadcast({...approve, testUid: 'other'}));
  assert.equal(f.sends.length, 1); assert.equal(f.docs.get('pushCampaigns/test-101').state, 'awaiting_approval');
});
test('approved broadcast reuses exact tested content and excludes Android, disabled and unrelated paths', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('owner'), 'users/other/pushDevices/b': ios('other'),
    'users/android/pushDevices/c': {token: 'android', enabled: true, platform: 'android'},
    'users/disabled/pushDevices/d': {...ios('disabled'), enabled: false}, 'other/x/pushDevices/z': ios('foreign')});
  await f.sender.test(testInput);
  const result = await f.sender.broadcast({...approve, title: 'unapproved', body: 'changed'});
  assert.equal(result.accepted, 2);
  assert.deepEqual(f.sends.map(m => m.token), ['owner', 'other', 'owner']);
  for (const message of f.sends) assert.deepEqual(message.notification, {title: testInput.title, body: testInput.body});
  assert.equal(f.docs.get('pushCampaigns/test-101').state, 'completed');
});
test('same test run or broadcast rerun never resends an already claimed campaign', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('owner')}); await f.sender.test(testInput);
  await assert.rejects(f.sender.test(testInput), /이미 실행/);
  await f.sender.broadcast(approve); await assert.rejects(f.sender.broadcast(approve));
  assert.equal(f.sends.length, 2);
});
test('two simultaneous approvals cannot broadcast twice', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('owner')}); await f.sender.test(testInput);
  const results = await Promise.allSettled([f.sender.broadcast(approve), f.sender.broadcast({...approve, runId: '103'})]);
  assert.equal(results.filter(x => x.status === 'fulfilled').length, 1); assert.equal(f.sends.length, 2);
});
test('latest token is re-read before sending and duplicate device tokens are sent once', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('old'), 'users/owner/pushDevices/b': ios('new')});
  const claim = f.store.claim;
  f.store.claim = async (...args) => {f.docs.set('users/owner/pushDevices/a', ios('new')); return claim(...args);};
  const result = await f.sender.test(testInput); assert.equal(result.accepted, 1);
  assert.deepEqual(f.sends.map(m => m.token), ['new']);
});
test('UNREGISTERED deletes only the rejected token and keeps a concurrently rotated token', async () => {
  for (const rotated of [false, true]) {
    const path = 'users/owner/pushDevices/a', f = fixture({[path]: ios('old')});
    const sender = createSender({store: f.store, send: async () => {
      if (rotated) f.docs.set(path, ios('new'));
      throw Object.assign(Error('token must not be logged'), {code: 'messaging/registration-token-not-registered'});
    }});
    await assert.rejects(sender.test(testInput));
    assert.equal(f.docs.has(path), rotated);
    if (rotated) assert.equal(f.docs.get(path).token, 'new');
    assert.equal([...f.docs].find(([path]) => path.includes('/testDeliveries/'))[1].status, 'invalid');
  }
});
test('ambiguous network failure does not delete tokens or automatically retry', async () => {
  const path = 'users/owner/pushDevices/a', f = fixture({[path]: ios('token')}); let attempts = 0;
  const sender = createSender({store: f.store, send: async () => {attempts++; throw Error('secret token');}});
  await assert.rejects(sender.test(testInput)); await assert.rejects(sender.test(testInput));
  assert.equal(attempts, 1); assert.ok(f.docs.has(path));
  const delivery = [...f.docs].find(([path]) => path.includes('/testDeliveries/'))[1];
  assert.equal(delivery.status, 'failed'); assert.equal(delivery.code, 'send-error'); assert.ok(!JSON.stringify(delivery).includes('secret'));
});
test('partially failed test cannot be approved for broadcast', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('good'), 'users/owner/pushDevices/b': ios('bad')});
  const sender = createSender({store: f.store, send: async message => {
    if (message.token === 'bad') throw Error('offline'); return f.send(message);
  }});
  await assert.rejects(sender.test(testInput), /실패한 기기/);
  assert.equal(f.docs.get('pushCampaigns/test-101').testCounts.accepted, 1);
  await assert.rejects(sender.broadcast(approve)); assert.equal(f.sends.length, 1);
});
test('crash after send reservation never automatically resends on rerun', async () => {
  const f = fixture({'users/owner/pushDevices/a': ios('owner')});
  f.store.finish = async () => {throw Error('lost database connection after FCM acceptance');};
  await assert.rejects(f.sender.test(testInput)); await assert.rejects(f.sender.test(testInput));
  assert.equal(f.sends.length, 1);
  assert.equal([...f.docs].find(([path]) => path.includes('/testDeliveries/'))[1].status, 'reserved');
  await assert.rejects(f.sender.broadcast(approve));
});
test('pagination delivers beyond the first page without duplicate sends', async () => {
  const initial = {}; for (let i = 0; i < 105; i++) initial['users/owner/pushDevices/' + String(i).padStart(3, '0')] = ios('token-' + i);
  const f = fixture(initial), result = await f.sender.test(testInput);
  assert.equal(result.accepted, 105); assert.equal(new Set(f.sends.map(m => m.token)).size, 105);
});
test('invalid configuration and empty content never contact devices', async () => {
  for (const patch of [{testUid: ''}, {runId: '../x'}, {title: ''}, {body: 'x'.repeat(501)}]) {
    const f = fixture(); await assert.rejects(f.sender.test({...testInput, ...patch}));
    assert.equal(f.docs.size, 0); assert.equal(f.reads.length, 0); assert.equal(f.sends.length, 0);
  }
});
test('entrypoint refuses non-manual/non-owner/non-main runs before Firebase initialization', () => {
  const allowed = {GITHUB_EVENT_NAME: 'workflow_dispatch', GITHUB_REF: 'refs/heads/main', GITHUB_REPOSITORY: 'kimsco/kimsco.github.io', GITHUB_ACTOR: 'kimsco'};
  for (const patch of [{GITHUB_EVENT_NAME: 'push'}, {GITHUB_REF: 'refs/heads/feature'}, {GITHUB_ACTOR: 'other'}, {GITHUB_REPOSITORY: 'other/fork'}]) {
    const result = spawnSync(process.execPath, ['notification-server/run.mjs'], {cwd: new URL('../', import.meta.url), env: {...allowed, ...patch}, encoding: 'utf8'});
    assert.equal(result.status, 1); assert.match(result.stderr, /소유자의 main 수동 실행/);
  }
});
test('entrypoint fails clearly on missing setup without printing malformed credentials', () => {
  const base = {GITHUB_EVENT_NAME: 'workflow_dispatch', GITHUB_REF: 'refs/heads/main', GITHUB_REPOSITORY: 'kimsco/kimsco.github.io', GITHUB_ACTOR: 'kimsco'};
  let result = spawnSync(process.execPath, ['notification-server/run.mjs'], {cwd: new URL('../', import.meta.url), env: base, encoding: 'utf8'});
  assert.equal(result.status, 1); assert.match(result.stderr, /PUSH_TEST_UID/);
  result = spawnSync(process.execPath, ['notification-server/run.mjs'], {cwd: new URL('../', import.meta.url), env: {...base, PUSH_TEST_UID: 'owner', FIREBASE_SERVICE_ACCOUNT_JSON: 'private-credential-data'}, encoding: 'utf8'});
  assert.equal(result.status, 1); assert.match(result.stderr, /FIREBASE_SERVICE_ACCOUNT_JSON/); assert.ok(!result.stderr.includes('private-credential-data'));
});
