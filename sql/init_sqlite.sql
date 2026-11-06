-- SQLite 建表脚本（默认模式，common/db.py 会自动执行，这里留作查阅）

CREATE TABLE IF NOT EXISTS test_case (
  case_id TEXT PRIMARY KEY,
  module  TEXT,
  title   TEXT,
  source  TEXT DEFAULT 'manual'          -- manual / ai
);

CREATE TABLE IF NOT EXISTS bug (
  bug_id     TEXT PRIMARY KEY,
  case_id    TEXT,                       -- 关联用例编号，便于追溯
  severity   TEXT,                       -- P0-P4
  status     TEXT,                       -- open / fixed / closed
  title      TEXT,                       -- 一句话描述现象与预期
  created_at TEXT,
  closed_at  TEXT
);

CREATE TABLE IF NOT EXISTS run_result (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id   TEXT,
  status    TEXT,                        -- passed / failed
  cost_ms   INTEGER,
  http_code INTEGER,                     -- 实际返回的状态码，失败时便于定位
  message   TEXT,                        -- 失败原因（正常为空）
  run_at    TEXT,
  batch     TEXT                         -- 执行批次号，如 20261106_164257
);
