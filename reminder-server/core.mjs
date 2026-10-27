export const TEXT = '오늘은 운동을 가지 않으셨군요. 내일은 분발하세요.';
export const koreaDay = ms => new Date(ms + 9 * 3600000).toISOString().slice(0, 10);
export function timestamp(value) {
  const match = /^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z$/.exec(value || '');
  if (!match || !Number.isFinite(Date.parse(value))) throw Error('invalid-basis');
  return match[1] + '.' + (match[2] || '').padEnd(9, '0') + 'Z';
}
export function createStore(db) {
  return {
    register: (uid, id, subscription) => db.prepare(`INSERT INTO devices(uid,device_id,subscription,endpoint)
      SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM devices WHERE uid=?)<10 OR EXISTS(SELECT 1 FROM devices WHERE uid=? AND device_id=?)
      ON CONFLICT(uid,device_id) DO UPDATE SET subscription=excluded.subscription,endpoint=excluded.endpoint`)
      .bind(uid, id, JSON.stringify(subscription), subscription.endpoint, uid, uid, id).run(),
    remove: (uid, id) => db.prepare('DELETE FROM devices WHERE uid=? AND device_id=?').bind(uid, id).run(),
    async forget(uid) {
      await db.batch(['devices', 'activity', 'local_activity', 'initialized', 'deliveries'].map(table => db.prepare('DELETE FROM ' + table + ' WHERE uid=?').bind(uid)));
    },
    async activity(uid, day, hasRecord, basis, deviceId='legacy', hasLocalRecord=false) {
      await db.batch([
        db.prepare(`INSERT INTO activity(uid,day,has_record,basis) VALUES(?,?,?,?)
          ON CONFLICT(uid,day) DO UPDATE SET has_record=excluded.has_record,basis=excluded.basis WHERE excluded.basis>activity.basis`)
          .bind(uid, day, Number(hasRecord), timestamp(basis)),
        db.prepare(`INSERT INTO local_activity(uid,device_id,day,has_record,basis) VALUES(?,?,?,?,?) ON CONFLICT(uid,device_id,day) DO UPDATE SET has_record=excluded.has_record,basis=excluded.basis WHERE excluded.basis>local_activity.basis`).bind(uid,deviceId,day,Number(hasLocalRecord),timestamp(basis)),
        db.prepare('INSERT OR IGNORE INTO initialized(uid) VALUES(?)').bind(uid)
      ]);
    },
    eligible: async day => (await db.prepare(`SELECT d.* FROM devices d
      JOIN initialized i ON i.uid=d.uid LEFT JOIN activity a ON a.uid=d.uid AND a.day=?
      WHERE COALESCE(a.has_record,0)=0 AND NOT EXISTS(SELECT 1 FROM local_activity l WHERE l.uid=d.uid AND l.day=? AND l.has_record=1) AND NOT EXISTS(SELECT 1 FROM deliveries x WHERE x.uid=d.uid AND x.device_id=d.device_id AND x.day=?)
      ORDER BY d.id LIMIT 10`).bind(day, day, day).all()).results,
    // One atomic SQL statement checks current activity and reserves a device/day.
    claim: (device, day) => db.prepare(`INSERT INTO deliveries(uid,device_id,day,status)
      SELECT ?,?,?,'reserved' WHERE EXISTS(SELECT 1 FROM devices WHERE uid=? AND device_id=? AND endpoint=?)
      AND EXISTS(SELECT 1 FROM initialized WHERE uid=?)
      AND NOT EXISTS(SELECT 1 FROM activity WHERE uid=? AND day=? AND has_record=1)
      AND NOT EXISTS(SELECT 1 FROM local_activity WHERE uid=? AND day=? AND has_record=1)
      ON CONFLICT(uid,device_id,day) DO NOTHING RETURNING uid`)
      .bind(device.uid, device.device_id, day, device.uid, device.device_id, device.endpoint, device.uid, device.uid, day, device.uid, day).first(),
    finish: (device, day, status) => db.prepare('UPDATE deliveries SET status=? WHERE uid=? AND device_id=? AND day=?')
      .bind(status, device.uid, device.device_id, day).run(),
    removeInvalid: device => db.prepare('DELETE FROM devices WHERE uid=? AND device_id=? AND endpoint=?')
      .bind(device.uid, device.device_id, device.endpoint).run(),
    async prune(day) {
      const cutoff = koreaDay(Date.parse(day + 'T00:00:00Z') - 14 * 86400000);
      await db.batch(['activity', 'local_activity', 'deliveries'].map(table => db.prepare('DELETE FROM ' + table + ' WHERE day<?').bind(cutoff)));
    }
  };
}
export async function runReminder({store, send, time, enabled}) {
  const counts = {accepted: 0, failed: 0, invalid: 0, skipped: 0};
  // A deployment alone must never enable sending. UTC 13 = Korea 22.
  if (!enabled || new Date(time).getUTCHours() !== 13) return counts;
  const day = koreaDay(time);
  if (new Date(time).getUTCMinutes() === 0) await store.prune(day);
  for (const device of await store.eligible(day)) {
    if (!await store.claim(device, day)) { counts.skipped++; continue; }
    let status;
    try {
      const response = await send(JSON.parse(device.subscription), {
        notification: {title: 'To the Top', body: TEXT}, data: {receiverUid: device.uid, url: '/'},
        messageId: 'workout-reminder-' + day
      });
      if (response.status === 404 || response.status === 410) {
        await store.removeInvalid(device); status = 'invalid'; counts.invalid++;
      } else if (response.status >= 200 && response.status < 300) {
        status = 'accepted'; counts.accepted++;
      } else { status = 'failed-' + response.status; counts.failed++; }
    } catch (_) { status = 'failed-network'; counts.failed++; }
    // Never retry ambiguous sends; a reserved device/day prevents double delivery.
    await store.finish(device, day, status);
  }
  return counts;
}
