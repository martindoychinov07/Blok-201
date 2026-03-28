PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
  id TEXT PRIMARY KEY,
  primary_user_id TEXT NOT NULL REFERENCES users(id),
  full_name TEXT NOT NULL,
  dob TEXT,
  diagnosis_notes TEXT,
  preferences_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS caregivers (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  relation_type TEXT,
  notify_warning INTEGER NOT NULL DEFAULT 1,
  notify_critical INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  serial_no TEXT UNIQUE NOT NULL,
  model TEXT,
  firmware_version TEXT,
  last_seen_at TEXT,
  battery_pct REAL,
  status TEXT
);

CREATE TABLE IF NOT EXISTS people_profiles (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  name TEXT,
  person_type TEXT,
  relationship_to_patient TEXT,
  phone TEXT,
  notes TEXT,
  confidence REAL NOT NULL DEFAULT 0.5,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  device_id TEXT REFERENCES devices(id),
  started_at TEXT NOT NULL,
  ended_at TEXT,
  language TEXT,
  summary_text TEXT,
  summary_confidence REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcripts (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  patient_id TEXT NOT NULL REFERENCES patients(id),
  ts_start_ms INTEGER NOT NULL,
  ts_end_ms INTEGER NOT NULL,
  speaker_label TEXT,
  text TEXT NOT NULL,
  stt_engine TEXT NOT NULL,
  stt_confidence REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extracted_facts (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  conversation_id TEXT REFERENCES conversations(id),
  transcript_id TEXT REFERENCES transcripts(id),
  fact_type TEXT NOT NULL,
  subject_ref TEXT,
  predicate TEXT NOT NULL,
  object_value TEXT NOT NULL,
  temporal_context TEXT,
  confidence REAL NOT NULL,
  status TEXT NOT NULL,
  source_evidence TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  source_conversation_id TEXT REFERENCES conversations(id),
  title TEXT NOT NULL,
  details TEXT,
  due_at TEXT,
  recurrence_rule TEXT,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zones (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  name TEXT NOT NULL,
  center_lat REAL NOT NULL,
  center_lon REAL NOT NULL,
  radius_m REAL NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gps_events (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  device_id TEXT REFERENCES devices(id),
  ts TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  speed_mps REAL,
  accuracy_m REAL,
  inside_zone INTEGER,
  zone_id TEXT REFERENCES zones(id)
);

CREATE TABLE IF NOT EXISTS fall_events (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  device_id TEXT REFERENCES devices(id),
  ts TEXT NOT NULL,
  impact_g REAL NOT NULL,
  orientation_delta REAL,
  inactivity_sec INTEGER,
  confidence REAL NOT NULL,
  is_confirmed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  device_id TEXT REFERENCES devices(id),
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  triggered_at TEXT NOT NULL,
  acknowledged_by TEXT REFERENCES users(id),
  acknowledged_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_patient_time
ON alerts(patient_id, triggered_at DESC);

CREATE INDEX IF NOT EXISTS idx_gps_patient_ts
ON gps_events(patient_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_transcripts_conversation
ON transcripts(conversation_id);

CREATE INDEX IF NOT EXISTS idx_facts_patient_type
ON extracted_facts(patient_id, fact_type, status);
