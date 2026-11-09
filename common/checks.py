"""用例断言，runner.py 与 tests/test_api.py 共用。

抽出来的原因：同一套断言规则之前写了两遍（urllib 通道一遍、requests 通道一遍），
改一处漏一处就会出现「命令行绿、pytest 红」的假象。现在断言只在这里定义。
"""
import json


def parse_json(text):
    """响应不是合法 JSON 时返回空 dict，交给断言去判断。"""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {}


def check_case(case, status, text, payload):
    """按用例的 expect 断言，不符合就抛 AssertionError（消息里带排查信息）。"""
    expect = case["expect"]
    assert status == expect["status"], "%s 期望 HTTP %s，实际 %s，响应：%s" % (
        case["id"], expect["status"], status, (text or "")[:200])

    for key, want in (expect.get("json") or {}).items():
        got = payload.get(key)
        assert got == want, "%s 字段 %s 期望 %r，实际 %r" % (case["id"], key, want, got)

    if expect.get("data_not_empty"):
        assert payload.get("data"), "%s 期望 data 非空，实际 %r" % (
            case["id"], payload.get("data"))
