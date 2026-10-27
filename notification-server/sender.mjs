import {createHash} from 'node:crypto';

export const PROJECT_ID = 'rmpj-7ca13';
const invalidTokenCodes = new Set(['messaging/registration-token-not-registered']);
const digest = value => createHash('sha256').update(value).digest('hex');
export function notificationText(title, body) {
  if (typeof title !== 'string' || !title.trim() || title.length > 120 ||
      typeof body !== 'string' || !body.trim() || body.length > 500) {
    throw Error('제목은 1~120자, 내용은 1~500자로 입력해주세요.');
  }
  return {title: title.trim(), body: body.trim()};
}
export function deviceIdentity(path) {
  const match = /^users\/([^/]+)\/pushDevices\/([^/]+)$/.exec(path);
  return match ? {uid: match[1], id: match[2]} : null;
}

// Persistence and transport are injected. Tests never use real Firebase or FCM.
export function createSender({store, send, now = () => new Date().toISOString()}) {
  async function deliver(campaignId, phase, text, testUid) {
    const counts = {accepted: 0, invalid: 0, failed: 0, skipped: 0};
    const seen = new Set();
    for await (const device of store.devices(testUid)) {
      const identity = deviceIdentity(device.path);
      if (!identity || (testUid && identity.uid !== testUid)) { counts.skipped++; continue; }
      // Re-read and reserve inside a transaction. The query's token can already be stale.
      const claim = await store.claim(campaignId, phase, device.path);
      if (!claim) { counts.skipped++; continue; }
      const key = digest(claim.token);
      if (seen.has(key)) {
        await store.finish(campaignId, phase, claim.id, {status: 'skipped', at: now()});
        counts.skipped++; continue;
      }
      seen.add(key);
      let result;
      try {
        await send({token: claim.token, notification: text,
          data: {receiverUid: identity.uid, url: '/', campaignId},
          webpush: {headers: {Urgency: 'high', TTL: '3600'}, fcmOptions: {link: 'https://kimsco.github.io/'}}});
        result = {status: 'accepted', at: now()}; counts.accepted++;
      } catch (error) {
        const code = typeof error?.code === 'string' ? error.code : '';
        if (invalidTokenCodes.has(code)) {
          // Only remove a token the server explicitly marked UNREGISTERED, and only
          // if the same token is still stored. Never delete a newly rotated token.
          await store.removeInvalid(device.path, claim.token);
          result = {status: 'invalid', at: now(), code}; counts.invalid++;
        } else {
          // No automatic retry after an ambiguous network error: avoid double sends.
          result = {status: 'failed', at: now(), code: code.startsWith('messaging/') ? code : 'send-error'};
          counts.failed++;
        }
      }
      await store.finish(campaignId, phase, claim.id, result);
    }
    return counts;
  }
  async function test({runId, title, body, testUid}) {
    if (!/^\d+$/.test(runId || '')) throw Error('유효한 GitHub 실행 번호가 필요합니다.');
    if (typeof testUid !== 'string' || !testUid || /[\s/]/.test(testUid)) throw Error('PUSH_TEST_UID를 설정해주세요.');
    const text = notificationText(title, body), campaignId = 'test-' + runId;
    const created = await store.create(campaignId, {state: 'testing', text, textHash: digest(JSON.stringify(text)), testUid, createdAt: now()});
    if (!created) throw Error('이미 실행된 테스트입니다. 재실행으로 중복 발송하지 않습니다. 새 테스트를 시작해주세요.');
    try {
      const counts = await deliver(campaignId, 'test', text, testUid);
      await store.update(campaignId, {state: counts.accepted > 0 && !counts.failed ? 'awaiting_approval' : 'test_failed', testCounts: counts, testedAt: now()});
      if (!counts.accepted) throw Error('테스트 발송 접수에 성공한 아이폰 기기가 없습니다.');
      if (counts.failed) throw Error('테스트 발송에 실패한 기기가 있습니다. 전체 발송 전에 연결을 확인해주세요.');
      return {campaignId, ...counts};
    } catch (error) {
      await store.update(campaignId, {state: 'test_failed', finishedAt: now()}); throw error;
    }
  }
  async function broadcast({testRunId, approval, runId, testUid}) {
    if (approval !== 'SEND') throw Error('폰에서 수신과 내용을 확인한 뒤 SEND로 전체 발송을 승인해주세요.');
    if (!/^\d+$/.test(testRunId || '') || !/^\d+$/.test(runId || '')) throw Error('테스트 실행 번호가 필요합니다.');
    const campaignId = 'test-' + testRunId;
    const campaign = await store.approve(campaignId, {runId, testUid, at: now()});
    // The title/body come exclusively from the accepted test, never new broadcast inputs.
    const text = notificationText(campaign.text?.title, campaign.text?.body);
    if (digest(JSON.stringify(text)) !== campaign.textHash) throw Error('테스트 내용 검증에 실패했습니다.');
    try {
      const counts = await deliver(campaignId, 'broadcast', text);
      await store.update(campaignId, {state: counts.failed ? 'completed_with_errors' : 'completed', broadcastCounts: counts, finishedAt: now()});
      return {campaignId, ...counts};
    } catch (error) {
      await store.update(campaignId, {state: 'failed', finishedAt: now()}); throw error;
    }
  }
  return {test, broadcast};
}

// Firebase Admin adapter. No credentials or token values are written to run logs.
export function firestoreStore(db, documentId) {
  const campaign = id => db.collection('pushCampaigns').doc(id);
  return {
    async create(id, value) {
      try { await campaign(id).create(value); return true; }
      catch (error) { if (error.code === 6 || error.code === 'already-exists') return false; throw error; }
    },
    update: (id, patch) => campaign(id).update(patch),
    approve: (id, {runId, testUid, at}) => db.runTransaction(async tx => {
      const ref = campaign(id), snapshot = await tx.get(ref), value = snapshot.data();
      if (!snapshot.exists || value.state !== 'awaiting_approval' || !value.testCounts?.accepted || value.testUid !== testUid) {
        throw Error('이 계정으로 테스트 발송한 대기 중 알림만 승인할 수 있습니다. 이미 처리된 알림은 재발송하지 않습니다.');
      }
      tx.update(ref, {state: 'sending', approvalRunId: runId, approvedAt: at}); return value;
    }),
    async *devices(uid) {
      let query = (uid ? db.collection('users').doc(uid).collection('pushDevices') : db.collectionGroup('pushDevices'))
        .where('platform', '==', 'ios').where('enabled', '==', true).orderBy(documentId()).limit(100);
      let cursor, total = 0;
      for (;;) {
        const page = await (cursor ? query.startAfter(cursor) : query).get();
        if (page.empty) return;
        for (const doc of page.docs) {
          if (++total > 10000) throw Error('단일 발송 한도를 초과했습니다.');
          yield {path: doc.ref.path};
        }
        if (page.size < 100) return;
        cursor = page.docs.at(-1);
      }
    },
    claim: (id, phase, path) => db.runTransaction(async tx => {
      const ref = db.doc(path), snapshot = await tx.get(ref), value = snapshot.data(), identity = deviceIdentity(path);
      if (!identity || !snapshot.exists || value.enabled !== true || value.platform !== 'ios' || typeof value.token !== 'string' || !value.token) return null;
      const deliveryId = digest(identity.uid + '\0' + value.token);
      const delivery = campaign(id).collection(phase + 'Deliveries').doc(deliveryId);
      if ((await tx.get(delivery)).exists) return null;
      tx.create(delivery, {status: 'reserved', reservedAt: new Date().toISOString()});
      return {id: deliveryId, token: value.token};
    }),
    finish: (id, phase, deliveryId, value) => campaign(id).collection(phase + 'Deliveries').doc(deliveryId).update(value),
    removeInvalid: (path, token) => db.runTransaction(async tx => {
      const ref = db.doc(path), snapshot = await tx.get(ref);
      if (snapshot.exists && snapshot.data().token === token) tx.delete(ref);
    })
  };
}
