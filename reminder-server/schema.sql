CREATE TABLE IF NOT EXISTS devices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid TEXT NOT NULL, device_id TEXT NOT NULL,
  subscription TEXT NOT NULL, endpoint TEXT NOT NULL,
  UNIQUE(uid, device_id), UNIQUE(endpoint)
);
CREATE TABLE IF NOT EXISTS activity (
  uid TEXT NOT NULL, day TEXT NOT NULL, has_record INTEGER NOT NULL CHECK(has_record IN (0,1)),
  basis TEXT NOT NULL, PRIMARY KEY(uid, day)
);
CREATE TABLE IF NOT EXISTS local_activity (
  uid TEXT NOT NULL, device_id TEXT NOT NULL, day TEXT NOT NULL, has_record INTEGER NOT NULL CHECK(has_record IN (0,1)),
  basis TEXT NOT NULL, PRIMARY KEY(uid, device_id, day)
);
CREATE TABLE IF NOT EXISTS initialized (uid TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS deliveries (
  uid TEXT NOT NULL, device_id TEXT NOT NULL, day TEXT NOT NULL,
  status TEXT NOT NULL, PRIMARY KEY(uid, device_id, day)
);
CREATE INDEX IF NOT EXISTS activity_day ON activity(day);
CREATE INDEX IF NOT EXISTS deliveries_day ON deliveries(day);

CREATE TABLE IF NOT EXISTS preferences (
  uid TEXT PRIMARY KEY,
  minute_of_day INTEGER NOT NULL CHECK(minute_of_day>=0 AND minute_of_day<1440),
  effective_day TEXT NOT NULL DEFAULT '0000-01-01'
);

CREATE TABLE IF NOT EXISTS delivery_slots (
  uid TEXT NOT NULL, device_id TEXT NOT NULL, day TEXT NOT NULL,
  minute_of_day INTEGER NOT NULL CHECK(minute_of_day>=0 AND minute_of_day<1440),
  status TEXT NOT NULL, PRIMARY KEY(uid, device_id, day, minute_of_day)
);
CREATE INDEX IF NOT EXISTS delivery_slots_day ON delivery_slots(day);
