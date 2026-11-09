"""执行数据统计报告：读数据库，把历史执行结果汇总成一份可读报告。

用法：
    python report.py          # 终端打印汇总
    python report.py --md     # 同时写入 reports/report.md

统计口径：
    通过率 = 通过次数 / 总执行次数（同一用例多轮执行都计入，反映真实回归情况）
    P95    = 95% 的请求耗时低于该值
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from common import db  # noqa: E402
from common.stats import percentile  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

BAR = "=" * 62


def collect():
    """汇总数据库里的执行数据，返回 dict；库不存在或没数据时返回 None。"""
    db.init_db()
    total = db.query("SELECT COUNT(*) FROM run_result")[0][0]
    cases = db.query("SELECT COUNT(DISTINCT case_id) FROM run_result")[0][0]
    if not total:
        return None

    status_rows = dict(db.query(
        "SELECT status, COUNT(*) FROM run_result GROUP BY status"))
    costs = [row[0] or 0 for row in db.query("SELECT cost_ms FROM run_result")]

    # 按批次号统计「最近一次执行」；老数据没有批次号时退回按时间戳统计
    latest_batch = db.query("SELECT MAX(batch) FROM run_result")[0][0]
    if latest_batch:
        latest = dict(db.query(
            "SELECT status, COUNT(*) FROM run_result WHERE batch = {p} GROUP BY status",
            (latest_batch,)))
        latest_at = db.query(
            "SELECT MIN(run_at) FROM run_result WHERE batch = {p}", (latest_batch,))[0][0]
    else:
        latest_at = db.query("SELECT MAX(run_at) FROM run_result")[0][0]
        latest = dict(db.query(
            "SELECT status, COUNT(*) FROM run_result WHERE run_at = {p} GROUP BY status",
            (latest_at,)))
    latest_total = sum(latest.values())

    modules = db.query(
        "SELECT COALESCE(t.module, '未登记'), COUNT(DISTINCT r.case_id), "
        "       SUM(CASE WHEN r.status = 'passed' THEN 1 ELSE 0 END), COUNT(*) "
        "FROM run_result r LEFT JOIN test_case t ON t.case_id = r.case_id "
        "GROUP BY COALESCE(t.module, '未登记') ORDER BY 2 DESC")

    days = []
    for offset in range(6, -1, -1):
        day = (date.today() - timedelta(days=offset)).isoformat()
        rows = db.query(
            "SELECT status, COUNT(*) FROM run_result WHERE substr(run_at, 1, 10) = {p} "
            "GROUP BY status", (day,))
        passed = sum(n for s, n in rows if s == "passed")
        count = sum(n for _, n in rows)
        days.append((day, count, passed))

    failed_rows = db.query(
        "SELECT case_id, status, http_code, cost_ms, message, run_at FROM run_result "
        "WHERE status <> 'passed' ORDER BY id DESC LIMIT 10")

    bugs = db.query("SELECT status, COUNT(*) FROM bug GROUP BY status")
    bug_total = sum(n for _, n in bugs)
    bug_closed = sum(n for s, n in bugs if s == "closed")
    bug_avg = db.query(
        "SELECT AVG((julianday(closed_at) - julianday(created_at)) * 24) FROM bug "
        "WHERE closed_at IS NOT NULL AND closed_at <> ''")[0][0] if db._kind() == "sqlite" else None

    return {
        "total": total,
        "cases": cases,
        "passed": status_rows.get("passed", 0),
        "failed": total - status_rows.get("passed", 0),
        "rate": round(status_rows.get("passed", 0) * 100.0 / total, 1),
        "avg": round(sum(costs) / len(costs), 1),
        "p95": percentile(costs, 0.95),
        "max": max(costs) if costs else 0,
        "latest_at": latest_at,
        "latest_batch": latest_batch,
        "latest_total": latest_total,
        "latest_passed": latest.get("passed", 0),
        "modules": modules,
        "days": days,
        "failed_rows": failed_rows,
        "bug_total": bug_total,
        "bug_closed": bug_closed,
        "bug_avg_hours": round(bug_avg, 1) if bug_avg else None,
    }


def _render(data):
    lines = [
        "累计执行：%d 次，覆盖 %d 条用例（通过 %d，失败 %d，通过率 %s%%）" % (
            data["total"], data["cases"], data["passed"], data["failed"], data["rate"]),
        "耗时：平均 %sms，P95 %sms，最长 %sms" % (data["avg"], data["p95"], data["max"]),
        "最近一次执行：%s（批次 %s），%d 条 / 通过 %d" % (
            data["latest_at"], data["latest_batch"] or "-",
            data["latest_total"], data["latest_passed"]),
        "",
        "按模块：",
    ]
    for module, case_count, passed, count in data["modules"]:
        rate = round(passed * 100.0 / count, 1) if count else 0
        lines.append("  %-12s 用例 %2d 条，执行 %3d 次，通过率 %s%%" % (
            module, case_count, count, rate))
    lines += ["", "近 7 天："]
    for day, count, passed in data["days"]:
        bar = "#" * min(30, count)
        lines.append("  %s  执行 %2d 次  通过 %2d  %s" % (day, count, passed, bar))
    lines += ["", "缺陷台账：共 %d 条，已闭环 %d 条%s" % (
        data["bug_total"], data["bug_closed"],
        "，平均修复时长 %s 小时" % data["bug_avg_hours"] if data["bug_avg_hours"] else "")]
    if data["failed_rows"]:
        lines += ["", "最近失败（最多 10 条）："]
        for case_id, _status, code, cost, msg, run_at in data["failed_rows"]:
            lines.append("  %s  %s  HTTP %s  %sms  %s" % (
                run_at, case_id, code, cost, (msg or "")[:80]))
    return lines


def render_markdown(data):
    out = [
        "# 执行数据统计",
        "",
        "生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        "| 累计执行次数 | %d |" % data["total"],
        "| 覆盖用例数 | %d |" % data["cases"],
        "| 通过 / 失败 | %d / %d |" % (data["passed"], data["failed"]),
        "| 通过率 | %s%% |" % data["rate"],
        "| 平均耗时 | %sms |" % data["avg"],
        "| P95 耗时 | %sms |" % data["p95"],
        "| 最长耗时 | %sms |" % data["max"],
        "| 缺陷总数 / 已闭环 | %d / %d |" % (data["bug_total"], data["bug_closed"]),
        "",
        "## 按模块",
        "",
        "| 模块 | 用例数 | 执行次数 | 通过率 |",
        "| --- | --- | --- | --- |",
    ]
    for module, case_count, passed, count in data["modules"]:
        rate = round(passed * 100.0 / count, 1) if count else 0
        out.append("| %s | %d | %d | %s%% |" % (module, case_count, count, rate))
    out += ["", "## 近 7 天执行趋势", "", "| 日期 | 执行次数 | 通过 |", "| --- | --- | --- |"]
    for day, count, passed in data["days"]:
        out.append("| %s | %d | %d |" % (day, count, passed))
    if data["failed_rows"]:
        out += ["", "## 最近失败", "", "| 时间 | 用例 | 状态码 | 耗时 | 原因 |", "| --- | --- | --- | --- | --- |"]
        for case_id, _status, code, cost, msg, run_at in data["failed_rows"]:
            out.append("| %s | %s | %s | %sms | %s |" % (
                run_at, case_id, code, cost, (msg or "").replace("|", "\\|")[:80]))
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="执行数据统计报告")
    parser.add_argument("--md", action="store_true", help="同时写入 reports/report.md")
    args = parser.parse_args(argv)

    data = collect()
    print(BAR)
    print(" qa-automation 执行数据统计   %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(BAR)
    if data is None:
        print("数据库里还没有执行记录。先运行：python runner.py")
        print(BAR)
        return False
    for line in _render(data):
        print(line)
    if args.md:
        os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
        path = os.path.join(ROOT, "reports", "report.md")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_markdown(data))
        print()
        print("Markdown 报告已写入：%s" % path)
    print(BAR)
    return True


if __name__ == "__main__":
    main()
