"""缺陷台账：把「发现 → 修复 → 回归关闭」的过程记进 bug 表，留下可查的时间戳。

用法：
    python buglog.py record TC_ORDER_002 P2 "数量为 0 时返回 500，应返回 400"
    python buglog.py fix BUG-0001        # 研发改完，进入待回归
    python buglog.py close BUG-0001      # 回归通过，闭环（写入 closed_at）
    python buglog.py list                # 列出全部缺陷
    python buglog.py stats               # 缺陷数、关闭率、平均修复时长

没有这一步，简历里的「N 个 Bug 全部闭环」就只是说法；有了它，每次状态变更都有时间戳可查。
"""
import argparse
import os
import sys
import unicodedata
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from common import db  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

SEVERITIES = ("P0", "P1", "P2", "P3", "P4")


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(text))


def _pad(text, width):
    """按显示宽度补空格，避免中文把表格挤歪。"""
    text = str(text)
    return text + " " * max(0, width - _width(text))
STATUSES = ("open", "fixed", "closed")


def _now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _next_id():
    rows = db.query("SELECT bug_id FROM bug")
    used = 0
    for (bug_id,) in rows:
        try:
            used = max(used, int(str(bug_id).split("-")[-1]))
        except ValueError:
            continue
    return "BUG-%04d" % (used + 1)


def record(case_id, severity, title, status="open"):
    severity = severity.upper()
    if severity not in SEVERITIES:
        raise SystemExit("严重级别只能是 %s" % "/".join(SEVERITIES))
    db.init_db()
    exists = db.query("SELECT COUNT(*) FROM test_case WHERE case_id = {p}", (case_id,))[0][0]
    bug_id = _next_id()
    db.save_bug(bug_id, case_id, severity, status, title, _now())
    print("已登记缺陷 %s（用例 %s，级别 %s）%s" % (
        bug_id, case_id, severity, "" if exists else " [提示] 该用例编号不在 test_case 台账里"))
    print("  标题：%s" % title)
    print("  状态：%s    创建时间：%s" % (status, _now()))
    print("下一步：修复后用 python buglog.py close %s 完成闭环" % bug_id)
    return bug_id


def set_status(bug_id, status):
    db.init_db()
    rows = db.query("SELECT status, created_at FROM bug WHERE bug_id = {p}", (bug_id,))
    if not rows:
        raise SystemExit("没有找到缺陷 %s，先 python buglog.py list 看看现有编号" % bug_id)
    current = rows[0][0]
    closed_at = _now() if status == "closed" else None
    db.update_bug_status(bug_id, status, closed_at)
    print("缺陷 %s：%s → %s" % (bug_id, current, status))
    if status == "closed":
        print("  关闭时间：%s（可用于统计修复时长）" % closed_at)


def list_bugs():
    db.init_db()
    rows = db.query(
        "SELECT bug_id, case_id, severity, status, title, created_at, closed_at "
        "FROM bug ORDER BY bug_id")
    if not rows:
        print("缺陷台账为空。用 python buglog.py record <用例编号> <级别> \"<标题>\" 登记第一条。")
        return
    print("%s%s%s%s%s%s" % (
        _pad("缺陷号", 9), _pad("关联用例", 15), _pad("级别", 6),
        _pad("状态", 8), _pad("创建时间", 21), "标题"))
    print("-" * 78)
    for bug_id, case_id, severity, status, title, created, closed in rows:
        print("%s%s%s%s%s%s" % (
            _pad(bug_id, 9), _pad(case_id, 15), _pad(severity, 6),
            _pad(status, 8), _pad(created, 21), title or ""))
        if closed:
            print("%s%s%s%s%s" % (
                _pad("", 9), _pad("", 15), _pad("", 6), _pad("关闭于", 8), closed))


def stats():
    db.init_db()
    rows = db.query("SELECT status, COUNT(*) FROM bug GROUP BY status")
    if not rows:
        print("缺陷台账为空，暂无统计。")
        return
    by_status = dict(rows)
    total = sum(by_status.values())
    closed = by_status.get("closed", 0)
    print("缺陷总数：%d" % total)
    for status in STATUSES:
        print("  %-6s %d" % (status, by_status.get(status, 0)))
    print("关闭率：%s%%" % round(closed * 100.0 / total, 1))
    if db._kind() == "sqlite":
        hours = db.query(
            "SELECT AVG((julianday(closed_at) - julianday(created_at)) * 24) FROM bug "
            "WHERE closed_at IS NOT NULL AND closed_at <> ''")[0][0]
        if hours is not None:
            # 当天闭环的项目很多，按分钟展示比 0.0 小时直观
            if hours < 1:
                print("平均修复时长：%s 分钟（从登记到回归关闭）" % round(hours * 60, 1))
            else:
                print("平均修复时长：%s 小时（从登记到回归关闭）" % round(hours, 1))
    print("按级别：")
    for severity, count in db.query(
            "SELECT severity, COUNT(*) FROM bug GROUP BY severity ORDER BY severity"):
        print("  %-3s %d" % (severity, count))


def export(path="docs/bugs.md"):
    """把台账导出成 Markdown 快照。

    数据库（*.sqlite3）默认不进版本库，clone 的人看不到缺陷记录；
    导出成文本文件提交进仓库，证据才对别人可见。
    """
    db.init_db()
    rows = db.query(
        "SELECT bug_id, case_id, severity, status, title, created_at, closed_at "
        "FROM bug ORDER BY bug_id")
    if not rows:
        raise SystemExit("台账为空，没有可导出的记录")

    total = len(rows)
    closed = sum(1 for r in rows if r[3] == "closed")
    lines = [
        "# 缺陷台账快照",
        "",
        "> 由 `python buglog.py export` 从 `qa_results.sqlite3` 导出，"
        "数据库本身不入库，这份 Markdown 作为可查的证据提交。",
        "",
        "- 缺陷总数：%d，已关闭 %d，关闭率 %s%%" % (
            total, closed, round(closed * 100.0 / total, 1)),
        "",
        "| Bug | 关联用例 | 级别 | 状态 | 现象与预期 | 登记时间 | 关闭时间 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for bug_id, case_id, severity, status, title, created_at, closed_at in rows:
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            bug_id, case_id or "-", severity or "-", status,
            (title or "").replace("|", "\\|"), created_at or "-", closed_at or "-"))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("台账已导出：%s（%d 条，关闭率 %s%%）" % (
        os.path.abspath(path), total, round(closed * 100.0 / total, 1)))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="缺陷台账（零依赖）")
    sub = parser.add_subparsers(dest="command")

    p_record = sub.add_parser("record", help="登记一个缺陷")
    p_record.add_argument("case_id", help="关联的用例编号，如 TC_ORDER_002")
    p_record.add_argument("severity", help="严重级别 P0-P4")
    p_record.add_argument("title", help="一句话描述现象与预期")
    p_record.add_argument("--status", default="open", choices=STATUSES)

    p_fix = sub.add_parser("fix", help="标记为已修复，等待回归")
    p_fix.add_argument("bug_id")

    p_close = sub.add_parser("close", help="回归通过，闭环")
    p_close.add_argument("bug_id")

    sub.add_parser("list", help="列出全部缺陷")
    sub.add_parser("stats", help="缺陷统计")
    p_export = sub.add_parser("export", help="导出 Markdown 快照（默认 docs/bugs.md）")
    p_export.add_argument("path", nargs="?", default="docs/bugs.md")

    args = parser.parse_args(argv)
    if args.command == "record":
        record(args.case_id, args.severity, args.title, args.status)
    elif args.command == "fix":
        set_status(args.bug_id, "fixed")
    elif args.command == "close":
        set_status(args.bug_id, "closed")
    elif args.command == "list":
        list_bugs()
    elif args.command == "stats":
        stats()
    elif args.command == "export":
        export(args.path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
