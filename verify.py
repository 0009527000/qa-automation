"""一键自检：不用装任何第三方包，任何 Python 3.x 都能跑。

做的事：
  1. 从 cases/*.yaml 读取全部用例（自带极简 YAML 解析，没 PyYAML 也行）
  2. 自动拉起 mock 被测服务（已在运行就直接复用）
  3. 用标准库 urllib 逐条执行并断言，结果写进 run_result / test_case
  4. 打印逐条结果、汇总指标和数据库历史统计
  5. 生成 reports/run_report.md

Windows 双击 verify.bat，或 VS Code 里运行本文件，或命令行 python verify.py。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import report  # noqa: E402
import runner  # noqa: E402

BAR = "=" * 62


def main():
    print(BAR)
    print(" qa-automation 一键自检")
    print(" Python %s   %s" % (sys.version.split()[0], sys.executable))
    print(BAR)
    print("依赖检查：核心流程只用标准库，无需 pip install。")

    results, stats = runner.run_all()

    print()
    print("数据库历史统计：")
    data = report.collect()
    if data:
        for line in report._render(data):
            print(("  " + line).rstrip())
    else:
        print("  暂无历史记录")

    ok = stats["failed"] == 0 and stats["total"] > 0
    print()
    if ok:
        print("RESULT: PASS - 全部 %d 条用例通过（平均 %sms，P95 %sms）" % (
            stats["total"], stats["avg"], stats["p95"]))
    else:
        print("RESULT: FAIL - %d/%d 通过，请查看上面的失败详情" % (
            stats["passed"], stats["total"]))

    # 顺手出一份可视化报告，面试/周报直接用
    try:
        import htmlreport
        print()
        htmlreport.main([])
    except Exception as exc:  # 报告失败不影响用例结论
        print("HTML 报告生成失败（不影响用例结果）：%s" % exc)

    print(BAR)
    # 不用 sys.exit：VS Code 调试器会把 SystemExit 当成异常抛出来
    return ok


if __name__ == "__main__":
    main()
