SQL_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transcripts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT NOT NULL,
  transcript_id INTEGER,
  name TEXT NOT NULL,
  relationship TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE SET NULL,
  UNIQUE(patient_id, name, relationship)
);

CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT NOT NULL,
  transcript_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  doctor TEXT,
  time_text TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT NOT NULL,
  transcript_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  text TEXT NOT NULL,
  time_text TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT NOT NULL,
  transcript_id INTEGER NOT NULL,
  fact_type TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcripts_patient_time
  ON transcripts(patient_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_appointments_patient
  ON appointments(patient_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_reminders_patient
  ON reminders(patient_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_facts_patient
  ON facts(patient_id, fact_type, created_at DESC);
"""
