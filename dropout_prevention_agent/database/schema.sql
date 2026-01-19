PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
  student_id TEXT PRIMARY KEY,
  full_name TEXT,
  major TEXT,
  year_level INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS student_signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  current_gpa REAL NOT NULL,
  previous_gpa REAL,
  attendance_pct REAL NOT NULL,
  lms_last_active_days INTEGER NOT NULL,
  failed_modules_count INTEGER NOT NULL DEFAULT 0,
  missed_assessments_count INTEGER NOT NULL DEFAULT 0,
  course_load_credits INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'manual_entry',
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_student_signals_student_time
ON student_signals(student_id, as_of);

CREATE TABLE IF NOT EXISTS risk_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  score INTEGER NOT NULL,
  level TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'rule_based',
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_risk_snapshots_student_time
ON risk_snapshots(student_id, as_of);

CREATE TABLE IF NOT EXISTS recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  risk_score INTEGER NOT NULL,
  risk_level TEXT NOT NULL,
  recommended_actions_json TEXT NOT NULL,
  priority TEXT NOT NULL,
  explanation TEXT NOT NULL,
  model_used TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_student_time
ON recommendations(student_id, as_of);

CREATE TABLE IF NOT EXISTS interventions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  intervention_type TEXT NOT NULL,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'proposed',
  outcome TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_interventions_student_time
ON interventions(student_id, as_of);
