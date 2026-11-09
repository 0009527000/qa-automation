# -*- coding: utf-8 -*-
"""把执行数据渲染成一份可打印的单页 HTML 报告（零第三方依赖）。

数据全部来自数据库（qa_results.sqlite3 或 MySQL），不编造任何数字：
    run_result  最近一轮的逐条结果、耗时分布
    test_case   用例台账（用例数、模块分布）
    bug         缺陷台账（状态流转）

用法：
    python htmlreport.py            # 生成 reports/report.html
    python htmlreport.py --open     # 生成后自动用默认浏览器打开

产物是单文件（CSS/SVG 全内联，不依赖 CDN），可以直接右键打印成 PDF 当作品集。
"""
import argparse
import os
import sys
import webbrowser
from datetime import datetime
from string import Template

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from common import config, db  # noqa: E402
from common.stats import p95  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

OUT = os.path.join(ROOT, "reports", "report.html")


def _esc(text):
    return (str(text if text is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def collect():
    """从数据库取报告需要的全部数据。"""
    db.init_db()
    rows = db.query(
        "SELECT case_id, status, cost_ms, http_code, message, run_at, batch "
        "FROM run_result ORDER BY run_at"
    )
    batches = []
    for row in rows:
        if row[6] and row[6] not in batches:
            batches.append(row[6])
    latest = batches[-1] if batches else ""
    latest_rows = [r for r in rows if r[6] == latest]

    modules_of = {r[0]: r[1] for r in db.query("SELECT case_id, module FROM test_case")}
    names = {r[0]: r[1] for r in db.query("SELECT case_id, title FROM test_case")}
    bugs = db.query(
        "SELECT bug_id, case_id, severity, status, title, created_at, closed_at "
        "FROM bug ORDER BY bug_id"
    )

    costs = [int(r[2] or 0) for r in latest_rows]
    passed = sum(1 for r in latest_rows if r[1] == "passed")

    modules = {}
    for r in latest_rows:
        mod = modules_of.get(r[0], "other")
        item = modules.setdefault(mod, {"total": 0, "passed": 0})
        item["total"] += 1
        item["passed"] += 1 if r[1] == "passed" else 0

    # 本轮耗时分布：比「按天执行量」更能说明响应表现
    edges = [(0, 5, "<5ms"), (5, 10, "5–10ms"), (10, 20, "10–20ms"),
             (20, 50, "20–50ms"), (50, 10 ** 9, "≥50ms")]
    buckets = [{"label": label,
                "count": sum(1 for c in costs if low <= c < high)}
               for low, high, label in edges]

    return {
        "latest": latest,
        "latest_rows": latest_rows,
        "names": names,
        "modules": modules,
        "bugs": bugs,
        "costs": costs,
        "passed": passed,
        "total": len(latest_rows),
        "avg": round(sum(costs) / len(costs), 1) if costs else 0,
        "p95": p95(costs),
        "max": max(costs) if costs else 0,
        "elapsed": round(sum(costs) / 1000.0, 2),
        "runs": len(batches),
        "buckets": buckets,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "base_url": config.BASE_URL,
        "db_path": config.DB_PATH,
        "kind": "MySQL" if config.MYSQL_HOST else "SQLite",
    }


def _column_chart(items, value_key="total", width=520, height=176, color="#2f6df6"):
    """通用柱状图（纯 SVG，无 JS）。items 里的值取 item[value_key]。"""
    if not items:
        return ""
    peak = max([i[value_key] for i in items] + [1])
    gap = 16
    bar_w = (width - gap * (len(items) + 1)) / len(items)
    parts = []
    for idx, item in enumerate(items):
        value = item[value_key]
        h = max(2, (height - 46) * value / peak)
        x = gap + idx * (bar_w + gap)
        y = height - 28 - h
        parts.append(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s" opacity="%s"/>'
            % (x, y, bar_w, h, color, "0.95" if value else "0.15"))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" fill="#6b7280">%d</text>'
                     % (x + bar_w / 2, y - 6, value))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" fill="#9ca3af">%s</text>'
                     % (x + bar_w / 2, height - 10, _esc(item["label"])))
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img">%s</svg>'
            % (width, height, height, "".join(parts)))


def _module_bars(modules):
    """模块分布：横向条形，条长按用例数占比。"""
    total = sum(m["total"] for m in modules.values()) or 1
    rows = []
    for name, item in sorted(modules.items(), key=lambda kv: -kv[1]["total"]):
        pct = item["total"] * 100.0 / total
        rate = item["passed"] * 100.0 / item["total"] if item["total"] else 0
        rows.append(
            '<div class="mod-row"><div class="mod-name">%s</div>'
            '<div class="mod-track"><div class="mod-fill" style="width:%.1f%%"></div></div>'
            '<div class="mod-num">%d 条 · 通过率 %.0f%%</div></div>'
            % (_esc(name), pct, item["total"], rate))
    return "".join(rows)


TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>接口自动化测试报告 · ${generated}</title>
<style>
  :root {
    --ink: #111827; --muted: #6b7280; --line: #e5e7eb; --bg: #f6f7f9;
    --card: #ffffff; --accent: #2f6df6; --ok: #12805c; --ok-bg: #e7f6ef;
    --bad: #b3261e; --bad-bg: #fdeceb;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 14px/1.6 -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 28px 20px 60px; }
  h1 { font-size: 22px; margin: 0 0 6px; letter-spacing: .2px; }
  .sub { color: var(--muted); font-size: 12.5px; }
  .chips { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { background: #fff; border: 1px solid var(--line); border-radius: 999px;
          padding: 3px 10px; font-size: 12px; color: #374151; }
  .chip b { font-weight: 600; color: var(--ink); }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 18px 0; }
  .kpi { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
  .kpi .label { font-size: 12px; color: var(--muted); }
  .kpi .value { font-size: 26px; font-weight: 650; letter-spacing: -.5px; margin-top: 2px; }
  .kpi .hint { font-size: 11.5px; color: #9ca3af; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }
  .card h2 { font-size: 14px; margin: 0 0 12px; font-weight: 600; }
  .mod-row { display: grid; grid-template-columns: 64px 1fr 132px; gap: 10px;
             align-items: center; margin: 9px 0; font-size: 12.5px; }
  .mod-name { color: #374151; }
  .mod-track { background: #eef2f7; border-radius: 4px; height: 9px; overflow: hidden; }
  .mod-fill { height: 100%; background: var(--accent); border-radius: 4px; }
  .mod-num { color: var(--muted); text-align: right; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th { text-align: left; font-weight: 600; color: var(--muted); font-size: 12px;
       border-bottom: 1px solid var(--line); padding: 8px; background: #fafbfc; }
  td { border-bottom: 1px solid #f1f2f4; padding: 7px 8px; vertical-align: top; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.mono, .mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
  td.msg { color: var(--bad); }
  .fail-row { background: #fffafa; }
  .pill { display: inline-block; padding: 1px 7px; border-radius: 999px;
          font-size: 11px; font-weight: 600; letter-spacing: .3px; }
  .pill.pass { color: var(--ok); background: var(--ok-bg); }
  .pill.fail { color: var(--bad); background: var(--bad-bg); }
  .table-card { margin-top: 14px; }
  .table-wrap { max-height: 560px; overflow: auto; border-radius: 6px; }
  .empty { color: var(--muted); font-size: 12.5px; padding: 8px 0; }
  footer { margin-top: 18px; color: #9ca3af; font-size: 11.5px; line-height: 1.8; }
  code { background: #f3f4f6; padding: 1px 5px; border-radius: 4px; font-size: 11.5px; }
  @media print {
    body { background: #fff; }
    .wrap { max-width: none; padding: 0; }
    .table-wrap { max-height: none; overflow: visible; }
    tr, .card, .kpi { break-inside: avoid; }
  }
  @media (max-width: 760px) { .kpis { grid-template-columns: repeat(2, 1fr); } .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>接口自动化测试报告</h1>
    <div class="sub">Web/App 功能测试与自动化回归平台 · 生成于 ${generated}</div>
    <div class="chips">
      <span class="chip">被测服务 <b>${base_url}</b></span>
      <span class="chip">数据源 <b>${kind} · ${db_path}</b></span>
      <span class="chip">最近批次 <b>${latest}</b></span>
      <span class="chip">累计执行 <b>${runs} 轮</b></span>
    </div>
  </header>

  <section class="kpis">
    <div class="kpi"><div class="label">用例总数</div><div class="value">${total}</div>
      <div class="hint">覆盖 ${mod_count} 个模块</div></div>
    <div class="kpi"><div class="label">通过率</div><div class="value">${rate}</div>
      <div class="hint">通过 ${passed} / 失败 ${failed}</div></div>
    <div class="kpi"><div class="label">P95 响应</div><div class="value">${p95} ms</div>
      <div class="hint">平均 ${avg} ms · 最长 ${max} ms</div></div>
    <div class="kpi"><div class="label">本轮耗时</div><div class="value">${elapsed} s</div>
      <div class="hint">${total} 条接口用例</div></div>
  </section>

  <div class="grid">
    <div class="card">
      <h2>模块分布</h2>
      ${module_bars}
    </div>
    <div class="card">
      <h2>本轮耗时分布（${total} 条）</h2>
      ${trend_chart}
    </div>
  </div>

  <div class="card table-card">
    <h2>最近一轮逐条结果（${total} 条）</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th style="width:64px">结果</th><th style="width:132px">用例</th>
        <th>标题</th><th style="width:64px">状态码</th><th style="width:64px">耗时</th>
        <th style="width:180px">失败原因</th></tr></thead>
        <tbody>${result_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="card table-card">
    <h2>缺陷台账（${bug_count} 条）</h2>
    ${bug_block}
  </div>

  <footer>
    数据来源：<code>run_result</code> / <code>test_case</code> / <code>bug</code> 三张表，未做任何人工修饰。<br>
    重新生成：<code>python htmlreport.py</code> · 打印成 PDF：浏览器 Ctrl+P，勾选「背景图形」效果更好。<br>
    说明：耗时是接口层实测数据，不是压测结论；本轮为 mock 被测服务的回归结果。
  </footer>
</div>
</body>
</html>
""")


def render(t):
    rate = t["passed"] * 100.0 / t["total"] if t["total"] else 0.0

    result_rows = []
    for r in t["latest_rows"]:
        ok = r[1] == "passed"
        result_rows.append(
            '<tr class="%s"><td><span class="pill %s">%s</span></td>'
            '<td class="mono">%s</td><td>%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="msg">%s</td></tr>'
            % ("fail-row" if not ok else "",
               "pass" if ok else "fail",
               "PASS" if ok else "FAIL",
               _esc(r[0]), _esc(t["names"].get(r[0], "")),
               _esc(r[3]), _esc(r[2]),
               _esc(r[4] if not ok else "")))

    bug_rows = []
    for b in t["bugs"]:
        bug_rows.append(
            '<tr><td class="mono">%s</td><td class="mono">%s</td><td>%s</td>'
            '<td><span class="pill %s">%s</span></td><td>%s</td><td class="mono">%s</td></tr>'
            % (_esc(b[0]), _esc(b[1] or "-"), _esc(b[2] or "-"),
               "pass" if b[3] == "closed" else "fail", _esc(b[3]), _esc(b[4] or ""),
               _esc(b[6] or b[5] or "")))

    if bug_rows:
        bug_block = (
            '<div class="table-wrap"><table><thead><tr><th style="width:110px">Bug ID</th>'
            '<th style="width:132px">关联用例</th><th style="width:60px">级别</th>'
            '<th style="width:70px">状态</th><th>标题</th><th style="width:150px">关闭时间</th>'
            "</tr></thead><tbody>%s</tbody></table></div>" % "".join(bug_rows))
    else:
        bug_block = (
            '<div class="empty">暂无缺陷记录。用例全部通过时这里为空属于正常；'
            '登记命令：<code>python buglog.py record &lt;用例编号&gt; &lt;级别&gt; "&lt;标题&gt;"</code></div>')

    return TEMPLATE.substitute(
        generated=_esc(t["generated"]),
        base_url=_esc(t["base_url"]),
        kind=_esc(t["kind"]),
        db_path=_esc(t["db_path"]),
        latest=_esc(t["latest"] or "-"),
        runs=t["runs"],
        total=t["total"],
        mod_count=len(t["modules"]),
        rate="%.1f%%" % rate,
        passed=t["passed"],
        failed=t["total"] - t["passed"],
        p95=t["p95"],
        avg=t["avg"],
        max=t["max"],
        elapsed=t["elapsed"],
        module_bars=_module_bars(t["modules"]),
        trend_chart=_column_chart(t["buckets"], "count"),
        result_rows="".join(result_rows),
        bug_count=len(t["bugs"]),
        bug_block=bug_block,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成单页 HTML 测试报告")
    parser.add_argument("--open", action="store_true", help="生成后用默认浏览器打开")
    args = parser.parse_args(argv)

    data = collect()
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(data))

    print("报告已生成：%s" % OUT)
    print("  最近批次 %s：%d 条，通过 %d，P95 %sms，本轮 %ss"
          % (data["latest"] or "-", data["total"], data["passed"],
             data["p95"], data["elapsed"]))
    if args.open:
        webbrowser.open("file:///" + OUT.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
