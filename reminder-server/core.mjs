export const TEXT = '오늘은 운동을 가지 않으셨군요. 내일은 분발하세요.';
export const koreaMinute = ms => {const d=new Date(ms+9*3600000);return d.getUTCHours()*60+d.getUTCMinutes();};
export const koreaDay = ms => new Date(ms + 9 * 3600000).toISOString().slice(0, 10);
export function timestamp(value) {
  const match = /^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z$/.exec(value || '');
  if (!match || !Number.isFinite(Date.parse(value))) throw Error('invalid-basis');
  return match[1] + '.' + (match[2] || '').padEnd(9, '0') + 'Z';
}
export function createStore(db) {
  return {
    async preference(uid){const value=await db.prepare('SELECT minute_of_day FROM preferences WHERE uid=?').bind(uid).first();return {minuteOfDay:value?.minute_of_day??1320};},
    savePreference:(uid,minute,effectiveDay='0000-01-01')=>db.prepare('INSERT INTO preferences(uid,minute_of_day,effective_day) VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET minute_of_day=excluded.minute_of_day,effective_day=excluded.effective_day').bind(uid,minute,effectiveDay).run(),
    register: (uid, id, subscription) => db.prepare(`INSERT INTO devices(uid,device_id,subscription,endpoint)
      SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM devices WHERE uid=?)<10 OR EXISTS(SELECT 1 FROM devices WHERE uid=? AND device_id=?)
      ON CONFLICT(uid,device_id) DO UPDATE SET subscription=excluded.subscription,endpoint=excluded.endpoint`)
      .bind(uid, id, JSON.stringify(subscription), subscription.endpoint, uid, uid, id).run(),
    remove: (uid, id) => db.prepare('DELETE FROM devices WHERE uid=? AND device_id=?').bind(uid, id).run(),
    async forget(uid) {
      await db.batch(['devices', 'activity', 'local_activity', 'initialized', 'deliveries', 'delivery_slots', 'preferences'].map(table => db.prepare('DELETE FROM ' + table + ' WHERE uid=?').bind(uid)));
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
    eligible: async (day,minute=1320) => (await db.prepare(`SELECT d.*, COALESCE(p.minute_of_day,1320) AS scheduled_minute FROM devices d
      JOIN initialized i ON i.uid=d.uid LEFT JOIN activity a ON a.uid=d.uid AND a.day=? LEFT JOIN preferences p ON p.uid=d.uid
      WHERE COALESCE(p.effective_day,'0000-01-01')<=? AND ? BETWEEN COALESCE(p.minute_of_day,1320) AND MIN(COALESCE(p.minute_of_day,1320)+59,1439) AND COALESCE(a.has_record,0)=0 AND NOT EXISTS(SELECT 1 FROM local_activity l WHERE l.uid=d.uid AND l.day=? AND l.has_record=1) AND NOT EXISTS(SELECT 1 FROM delivery_slots x WHERE x.uid=d.uid AND x.device_id=d.device_id AND x.day=? AND x.minute_of_day=COALESCE(p.minute_of_day,1320))
      ORDER BY d.id LIMIT 10`).bind(day, day, minute, day, day).all()).results,
    // Reserve the selected time atomically; reject a candidate if preferences changed.
    claim: (device, day, minute=1320) => db.prepare(`INSERT INTO delivery_slots(uid,device_id,day,minute_of_day,status)
      SELECT ?,?,?,?,'reserved' WHERE EXISTS(SELECT 1 FROM devices WHERE uid=? AND device_id=? AND endpoint=?)
      AND EXISTS(SELECT 1 FROM initialized WHERE uid=?)
      AND COALESCE((SELECT effective_day FROM preferences WHERE uid=?),'0000-01-01')<=?
      AND COALESCE((SELECT minute_of_day FROM preferences WHERE uid=?),1320)=?
      AND ? BETWEEN ? AND MIN(?+59,1439)
      AND NOT EXISTS(SELECT 1 FROM activity WHERE uid=? AND day=? AND has_record=1)
      AND NOT EXISTS(SELECT 1 FROM local_activity WHERE uid=? AND day=? AND has_record=1)
      ON CONFLICT(uid,device_id,day,minute_of_day) DO NOTHING RETURNING uid`)
      .bind(device.uid, device.device_id, day, device.scheduled_minute, device.uid, device.device_id, device.endpoint,
        device.uid, device.uid, day, device.uid, device.scheduled_minute, minute, device.scheduled_minute, device.scheduled_minute,
        device.uid, day, device.uid, day).first(),
    finish: (device, day, status) => db.prepare('UPDATE delivery_slots SET status=? WHERE uid=? AND device_id=? AND day=? AND minute_of_day=?')
      .bind(status, device.uid, device.device_id, day, device.scheduled_minute).run(),
    removeInvalid: device => db.prepare('DELETE FROM devices WHERE uid=? AND device_id=? AND endpoint=?')
      .bind(device.uid, device.device_id, device.endpoint).run(),
    async prune(day) {
      const cutoff = koreaDay(Date.parse(day + 'T00:00:00Z') - 14 * 86400000);
      await db.batch(['activity', 'local_activity', 'deliveries', 'delivery_slots'].map(table => db.prepare('DELETE FROM ' + table + ' WHERE day<?').bind(cutoff)));
    }
  };
}
export async function runReminder({store, send, time, enabled}) {
  const counts = {accepted: 0, failed: 0, invalid: 0, skipped: 0};
  // A deployment alone must never enable sending. Times are stored in Korea minutes.
  if (!enabled || !Number.isFinite(time)) return counts;
  const day = koreaDay(time),minute=koreaMinute(time);
  if (minute===0) await store.prune(day);
  for (const device of await store.eligible(day,minute)) {
    if (!await store.claim(device, day,minute)) { counts.skipped++; continue; }
    let status;
    try {
      const response = await send(JSON.parse(device.subscription), {
        notification: {title: '', body: TEXT}, data: {receiverUid: device.uid, url: '/'},
        messageId: 'workout-reminder-' + day + '-' + device.scheduled_minute
      });
      if (response.status === 404 || response.status === 410) {
        await store.removeInvalid(device); status = 'invalid'; counts.invalid++;
      } else if (response.status >= 200 && response.status < 300) {
        status = 'accepted'; counts.accepted++;
      } else { status = 'failed-' + response.status; counts.failed++; }
    } catch (error) { status = /^failed-(prepare|fetch)-(TypeError|OperationError|DataError|NotSupportedError|InvalidAccessError|TimeoutError|AbortError|Error)$/.test(error?.reminderFailure || '') ? error.reminderFailure : 'failed-network'; counts.failed++; }
    // Never retry ambiguous sends; a reserved device/day/time prevents double delivery.
    await store.finish(device, day, status);
  }
  return counts;
}
