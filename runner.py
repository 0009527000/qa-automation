"""用例执行器：零第三方依赖。

读 cases/*.yaml → 逐个发请求 → 断言状态码与响应字段 → 结果（含失败）落库 →
打印逐条结果与汇总 → 追加一份 Markdown 报告到 reports/。

用法（不用装任何包，任何 Python 3.x 都能跑）：
    python runner.py                 # 跑全部用例
    python runner.py --tag smoke     # 只跑冒烟用例
    python runner.py --tag regression
    python runner.py --no-server     # 被测服务已自行启动，不要自动拉起 mock

VS Code 里直接右键 runner.py → Run Python File，或按 F5（.vscode/launch.json 已配好）。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from common import cases as case_loader  # noqa: E402
from common import db  # noqa: E402
from common.config import API_TOKEN, BASE_URL, REQUEST_TIMEOUT  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")  # 防止个别字符在 GBK 控制台崩掉
    except Exception:
        pass

BAR = "=" * 62


def _request(case):
    """发一次请求，返回 (http_code, payload_text, payload_dict)。"""
    url = BASE_URL + case["path"]
    if case.get("params"):
        url += "?" + urllib.parse.urlencode(case["params"])
    data = None
    if case.get("body") is not None:
        data = json.dumps(case["body"]).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=case["method"].upper())
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Token", API_TOKEN)  # 用例里的 headers 会覆盖它（含置空）
    for key, value in (case.get("headers") or {}).items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:  # 4xx/5xx 是预期结果之一，不当异常抛
        status, raw = exc.code, exc.read()

    text = raw.decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except ValueError:
        payload = {}
    return status, text, payload


def _check(case, status, text, payload):
    """断言；不符合预期就抛 AssertionError，消息里带足排查信息。"""
    expect = case["expect"]
    assert status == expect["status"], "%s 期望 HTTP %s，实际 %s，响应：%s" % (
        case["id"], expect["status"], status, text[:200])
    for key, want in (expect.get("json") or {}).items():
        got = payload.get(key)
        assert got == want, "%s 字段 %s 期望 %r，实际 %r" % (case["id"], key, want, got)
    if expect.get("data_not_empty"):
        assert payload.get("data"), "%s 期望 data 非空，实际 %r" % (
            case["id"], payload.get("data"))


def _run_one(case, batch=""):
    start = time.perf_counter()
    status_code = 0
    try:
        status_code, text, payload = _request(case)
        _check(case, status_code, text, payload)
        status, message = "passed", ""
    except Exception as exc:
        status, message = "failed", "%s: %s" % (type(exc).__name__, exc)
    cost_ms = round((time.perf_counter() - start) * 1000)
    db.save_result(case["id"], status, cost_ms, status_code, message, batch)
    return {
        "id": case["id"],
        "name": case.get("name", ""),
        "module": case.get("module", ""),
        "tags": case.get("tags") or [],
        "status": status,
        "cost_ms": cost_ms,
        "http_code": status_code,
        "message": message,
    }


def _reachable(base, timeout=1.0):
    try:
        urllib.request.urlopen(base + "/api/query?keyword=ping", timeout=timeout).read()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def _start_server():
    """被测服务没起来就拉起 mock_server.py，返回进程对象（自己启动的才负责关）。"""
    if _reachable(BASE_URL):
        print("被测服务已在运行：%s（复用，不重复启动）" % BASE_URL)
        return None
    print("被测服务未启动，正在拉起 mock_server.py ...")
    proc = subprocess.Popen(
        [sys.executable, "mock_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if _reachable(BASE_URL, timeout=0.5):
            return proc
        if proc.poll() is not None:
            raise RuntimeError("mock_server.py 启动失败，请手动运行 python mock_server.py 查看报错")
        time.sleep(0.25)
    proc.terminate()
    raise RuntimeError("等待 %s 超时，端口可能被占用" % BASE_URL)


def _stats(results):
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    costs = sorted(r["cost_ms"] for r in results)
    avg = round(sum(costs) / total, 1) if total else 0
    p95 = costs[min(total - 1, int(round(0.95 * (total - 1))))] if total else 0
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "rate": round(passed * 100.0 / total, 1) if total else 0.0,
        "avg": avg,
        "p95": p95,
        "max": costs[-1] if costs else 0,
        "elapsed_ms": sum(costs),
    }


def _print_results(results, stats):
    print()
    print("%-8s %-14s %-6s %-8s %s" % ("结果", "用例", "状态码", "耗时", "标题"))
    print("-" * 62)
    for r in results:
        mark = "[PASS]" if r["status"] == "passed" else "[FAIL]"
        print("%-8s %-14s %-6s %-8s %s" % (
            mark, r["id"], r["http_code"], "%sms" % r["cost_ms"], r["name"]))
        if r["status"] == "failed":
            print("         -> %s" % r["message"])
    print("-" * 62)
    print("用例 %d 条：通过 %d，失败 %d，通过率 %s%%" % (
        stats["total"], stats["passed"], stats["failed"], stats["rate"]))
    print("耗时：平均 %sms，P95 %sms，最长 %sms" % (
        stats["avg"], stats["p95"], stats["max"]))
    # 手工逐条点一遍通常 20-60 秒，这里给出与手工的直观对照
    if stats["elapsed_ms"]:
        print("本次自动化执行总耗时 %ss（手工逐条执行通常需要数分钟）" % (
            round(stats["elapsed_ms"] / 1000.0, 2)))


def _write_markdown(results, stats, tag, batch=""):
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    path = os.path.join(ROOT, "reports", "run_report.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 用例执行报告",
        "",
        "- 执行时间：%s" % now,
        "- 批次号：%s" % (batch or "-"),
        "- 被测服务：%s" % BASE_URL,
        "- 用例范围：%s" % (tag or "全部"),
        "- 结果：共 %d 条，通过 %d，失败 %d，通过率 %s%%" % (
            stats["total"], stats["passed"], stats["failed"], stats["rate"]),
        "- 耗时：平均 %sms，P95 %sms，最长 %sms" % (
            stats["avg"], stats["p95"], stats["max"]),
        "",
        "| 用例 | 模块 | 结果 | 状态码 | 耗时(ms) | 标题 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["id"], r["module"], r["status"], r["http_code"], r["cost_ms"], r["name"]))
    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        lines += ["", "## 失败详情", ""]
        for r in failed:
            lines.append("- **%s** %s" % (r["id"], r["message"]))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run_all(tag=None, auto_server=True, verbose=True):
    """执行用例并返回 (results, stats)。供 runner.py / verify.py 共用。"""
    all_cases = case_loader.load_cases()
    selected = case_loader.filter_by_tag(all_cases, tag)
    if not selected:
        raise SystemExit("没有匹配 --tag %s 的用例" % tag)

    db.init_db()
    db.sync_cases(selected)
    proc = _start_server() if auto_server else None
    batch = datetime.now().strftime("%Y%m%d_%H%M%S")
    if verbose:
        print()
        print("批次 %s" % batch)
        print("执行 %d 条用例（共 %d 条，范围：%s）" % (
            len(selected), len(all_cases), tag or "全部"))
    try:
        results = [_run_one(case, batch) for case in selected]
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    stats = _stats(results)
    if verbose:
        _print_results(results, stats)
        path = _write_markdown(results, stats, tag, batch)
        print("报告已写入：%s" % path)
        print("结果已写入数据库：%s（run_result / test_case）" % os.path.abspath(db.config.DB_PATH))
    return results, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="零依赖用例执行器")
    parser.add_argument("--tag", help="只跑带该标签的用例，如 smoke / regression")
    parser.add_argument("--no-server", action="store_true", help="不自动启动 mock 被测服务")
    args = parser.parse_args(argv)

    print(BAR)
    print(" qa-automation 用例执行器   Python %s" % sys.version.split()[0])
    print(BAR)

    results, stats = run_all(tag=args.tag, auto_server=not args.no_server)
    ok = stats["failed"] == 0
    print()
    print("RESULT: %s - %d/%d passed" % ("PASS" if ok else "FAIL", stats["passed"], stats["total"]))
    print(BAR)
    # 不用 sys.exit：VS Code 调试器会把 SystemExit 显示成异常，影响阅读
    return ok


if __name__ == "__main__":
    main()
