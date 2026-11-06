-- SQLite 建表脚本（默认模式，common/db.py 会自动执行，这里留作查阅）

CREATE TABLE IF NOT EXISTS test_case (
  case_id TEXT PRIMARY KEY,
  module  TEXT,
  title   TEXT,
  source  TEXT DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS bug (
  bug_id     TEXT PRIMARY KEY,
  case_id    TEXT,
  severity   TEXT,
  status     TEXT,
  created_at TEXT,
  closed_at  TEXT
);

CREATE TABLE IF NOT EXISTS run_result (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id   TEXT,
  status    TEXT,
  cost_ms   INTEGER,
  http_code INTEGER,
  message   TEXT,
  run_at    TEXT
);
