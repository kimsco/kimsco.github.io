CREATE TABLE IF NOT EXISTS delivery_slots (
  uid TEXT NOT NULL, device_id TEXT NOT NULL, day TEXT NOT NULL,
  minute_of_day INTEGER NOT NULL CHECK(minute_of_day>=0 AND minute_of_day<1440),
  status TEXT NOT NULL, PRIMARY KEY(uid, device_id, day, minute_of_day)
);
CREATE INDEX IF NOT EXISTS delivery_slots_day ON delivery_slots(day);

-- Old deliveries did not store the time. Preserve today's current setting as
-- handled; selecting a different future time enables a new delivery.
-- Running this migration again must not reinterpret old history at a new time.
INSERT OR IGNORE INTO delivery_slots(uid, device_id, day, minute_of_day, status)
SELECT d.uid, d.device_id, d.day, COALESCE(p.minute_of_day,1320), d.status
FROM deliveries d LEFT JOIN preferences p ON p.uid=d.uid
WHERE NOT EXISTS (
  SELECT 1 FROM delivery_slots s
  WHERE s.uid=d.uid AND s.device_id=d.device_id AND s.day=d.day
);
