"""执行结果与缺陷台账落库。

默认 SQLite（零配置即可跑）；设置 MYSQL_HOST 后切 MySQL（需 PyMySQL）。
三张表：
  test_case  用例台账（每次执行前从 cases/*.yaml 同步）
  bug        缺陷记录与状态流转（open → fixed → closed，带时间戳）
  run_result 每次执行结果（成功与失败都记，避免只统计通过用例造成数据失真）

SQL 里用 {p} 表示参数占位符，由 query()/execute() 自动换成 ? 或 %s，
所以上层脚本不用关心当前连的是哪种数据库。
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
         title      TEXT,
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
         run_at    TEXT,
         batch     TEXT
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
         title      VARCHAR(128),
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
         batch     VARCHAR(32),
         INDEX idx_case_run (case_id, run_at)
       )""",
]


def _now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


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


def _prepare(sql, kind):
    return sql.replace("{p}", "?" if kind == "sqlite" else "%s")


def query(sql, args=()):
    """执行查询并返回全部行（参数占位符用 {p}）。"""
    conn, kind = connect()
    try:
        cur = conn.cursor()
        cur.execute(_prepare(sql, kind), args)
        return cur.fetchall()
    finally:
        conn.close()


def execute(sql, args=()):
    """执行写入语句并提交。"""
    conn, kind = connect()
    try:
        cur = conn.cursor()
        cur.execute(_prepare(sql, kind), args)
        conn.commit()
    finally:
        conn.close()


def init_db():
    """建表；老库如果缺 bug.title 列则补上（轻量迁移，不删数据）。"""
    conn, kind = connect()
    try:
        cur = conn.cursor()
        for ddl in (MYSQL_DDL if kind == "mysql" else SQLITE_DDL):
            cur.execute(ddl)
        conn.commit()
        _migrate(conn, kind)
    finally:
        conn.close()


def _ensure_column(cur, kind, table, column, ddl_type):
    """轻量迁移：列不存在就补上，老库不用重建。"""
    try:
        if kind == "sqlite":
            cols = [row[1] for row in cur.execute("PRAGMA table_info(%s)" % table).fetchall()]
            if column not in cols:
                cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl_type))
        else:
            try:
                cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl_type))
            except Exception:
                pass
    except Exception:
        pass


def _migrate(conn, kind):
    cur = conn.cursor()
    try:
        if kind == "sqlite":
            cols = [row[1] for row in cur.execute("PRAGMA table_info(bug)").fetchall()]
            if "title" not in cols:
                cur.execute("ALTER TABLE bug ADD COLUMN title TEXT")
        else:
            try:
                cur.execute("ALTER TABLE bug ADD COLUMN title VARCHAR(128)")
            except Exception:  # 列已存在
                pass
        _ensure_column(cur, kind, "run_result", "batch",
                       "TEXT" if kind == "sqlite" else "VARCHAR(32)")
        conn.commit()
    except Exception:
        pass


def sync_cases(cases, source="yaml"):
    """把 YAML 用例同步进 test_case 台账，保证表里的用例数与文件一致。"""
    sql = (
        "INSERT OR REPLACE INTO test_case (case_id, module, title, source) "
        "VALUES ({p}, {p}, {p}, {p})"
        if _kind() == "sqlite"
        else "REPLACE INTO test_case (case_id, module, title, source) "
             "VALUES ({p}, {p}, {p}, {p})"
    )
    conn, kind = connect()
    try:
        cur = conn.cursor()
        cur.executemany(
            _prepare(sql, kind),
            [(c["id"], c.get("module", ""), c.get("name", ""), source) for c in cases],
        )
        conn.commit()
    finally:
        conn.close()


def _kind():
    return "mysql" if config.MYSQL_HOST else "sqlite"


def save_result(case_id, status, cost_ms, http_code, message="", batch=""):
    """成功与失败都记录，避免只统计通过的用例造成数据失真。

    batch 是一轮执行的批次号（如 20261106_164257），用来精确统计「最近一次执行」，
    避免同一轮里跨秒导致分组错乱。
    """
    execute(
        "INSERT INTO run_result (case_id, status, cost_ms, http_code, message, run_at, batch) "
        "VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})",
        (case_id, status, int(cost_ms), int(http_code), (message or "")[:500], _now(), batch),
    )


def save_bug(bug_id, case_id, severity, status, title, created_at, closed_at=None):
    execute(
        "INSERT INTO bug (bug_id, case_id, severity, status, title, created_at, closed_at) "
        "VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})",
        (bug_id, case_id, severity, status, title, created_at, closed_at),
    )


def update_bug_status(bug_id, status, closed_at=None):
    execute(
        "UPDATE bug SET status = {p}, closed_at = {p} WHERE bug_id = {p}",
        (status, closed_at, bug_id),
    )
