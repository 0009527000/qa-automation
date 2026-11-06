"""执行结果落库。

默认 SQLite（零配置即可跑）；设置 MYSQL_HOST 后切换 MySQL。
三张表：test_case（用例）/ bug（缺陷状态流转）/ run_result（每次执行结果）。
"""
import sqlite3
from datetime import datetime

from common import config

SQLITE_DDL = [
    """CREATE TABLE IF NOT EXISTS test_case (
         case_id TEXT PRIMARY KEY,
         module  TEXT,
         title   TEXT,
         source  TEXT DEFAULT 'manual'
       )""",
    """CREATE TABLE IF NOT EXISTS bug (
         bug_id     TEXT PRIMARY KEY,
         case_id    TEXT,
         severity   TEXT,
         status     TEXT,
         created_at TEXT,
         closed_at  TEXT
       )""",
    """CREATE TABLE IF NOT EXISTS run_result (
         id        INTEGER PRIMARY KEY AUTOINCREMENT,
         case_id   TEXT,
         status    TEXT,
         cost_ms   INTEGER,
         http_code INTEGER,
         message   TEXT,
         run_at    TEXT
       )""",
]

MYSQL_DDL = [
    """CREATE TABLE IF NOT EXISTS test_case (
         case_id VARCHAR(32) PRIMARY KEY,
         module  VARCHAR(32),
         title   VARCHAR(128),
         source  VARCHAR(16) DEFAULT 'manual'
       )""",
    """CREATE TABLE IF NOT EXISTS bug (
         bug_id     VARCHAR(32) PRIMARY KEY,
         case_id    VARCHAR(32),
         severity   VARCHAR(16),
         status     VARCHAR(16),
         created_at DATETIME,
         closed_at  DATETIME
       )""",
    """CREATE TABLE IF NOT EXISTS run_result (
         id        BIGINT AUTO_INCREMENT PRIMARY KEY,
         case_id   VARCHAR(32),
         status    VARCHAR(16),
         cost_ms   INT,
         http_code INT,
         message   VARCHAR(512),
         run_at    DATETIME,
         INDEX idx_case_run (case_id, run_at)
       )""",
]


def connect():
    """返回 (connection, kind)，kind 为 sqlite / mysql。"""
    if config.MYSQL_HOST:
        import pymysql

        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset="utf8mb4",
        )
        return conn, "mysql"
    return sqlite3.connect(config.DB_PATH), "sqlite"


def init_db():
    conn, kind = connect()
    try:
        cur = conn.cursor()
        for ddl in (MYSQL_DDL if kind == "mysql" else SQLITE_DDL):
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()


def save_result(case_id, status, cost_ms, http_code, message=""):
    """成功与失败都记录，避免只统计通过的用例造成数据失真。"""
    conn, kind = connect()
    ph = "?" if kind == "sqlite" else "%s"
    sql = (
        "INSERT INTO run_result "
        "(case_id, status, cost_ms, http_code, message, run_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)" % (ph, ph, ph, ph, ph, ph)
    )
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    try:
        cur = conn.cursor()
        cur.execute(sql, (case_id, status, cost_ms, http_code, (message or "")[:500], now))
        conn.commit()
    finally:
        conn.close()
