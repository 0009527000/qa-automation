"""参数化执行每条用例：请求 → 断言 → 结果（成功/失败都）落库。"""
import time

from common import db


def test_api(case, client, batch):
    start = time.perf_counter()
    status = "passed"
    http_code = 0
    message = ""

    try:
        resp = client.request(
            case["method"],
            case["path"],
            json=case.get("body"),
            params=case.get("params"),
            headers=case.get("headers"),
        )
        http_code = resp.status_code
        expect = case["expect"]

        assert http_code == expect["status"], (
            "%s 期望 HTTP %s，实际 %s，响应：%s"
            % (case["id"], expect["status"], http_code, resp.text[:200])
        )

        payload = resp.json()
        for key, value in expect.get("json", {}).items():
            assert payload.get(key) == value, (
                "%s 字段 %s 期望 %r，实际 %r"
                % (case["id"], key, value, payload.get(key))
            )
        if expect.get("data_not_empty"):
            assert payload.get("data"), "%s 期望 data 非空" % case["id"]

    except Exception as exc:
        status = "failed"
        message = str(exc)
        raise
    finally:
        cost_ms = round((time.perf_counter() - start) * 1000)
        db.save_result(case["id"], status, cost_ms, http_code, message, batch)
