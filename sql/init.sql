-- MySQL 建表脚本：切换到 MySQL 时先在目标库执行本文件
-- CREATE DATABASE IF NOT EXISTS qa_automation DEFAULT CHARSET utf8mb4;
-- USE qa_automation;

CREATE TABLE IF NOT EXISTS test_case (
  case_id VARCHAR(32) PRIMARY KEY,
  module  VARCHAR(32),
  title   VARCHAR(128),
  source  VARCHAR(16) DEFAULT 'manual'   -- manual / ai
);

CREATE TABLE IF NOT EXISTS bug (
  bug_id     VARCHAR(32) PRIMARY KEY,
  case_id    VARCHAR(32),
  severity   VARCHAR(16),                -- P0-P4
  status     VARCHAR(16),                -- open / fixed / closed
  title      VARCHAR(128),               -- 一句话描述现象与预期
  created_at DATETIME,
  closed_at  DATETIME
);

CREATE TABLE IF NOT EXISTS run_result (
  id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  case_id   VARCHAR(32),
  status    VARCHAR(16),                 -- passed / failed
  cost_ms   INT,
  http_code INT,
  message   VARCHAR(512),
  run_at    DATETIME,
  batch     VARCHAR(32),                 -- 执行批次号
  INDEX idx_case_run (case_id, run_at)
);
