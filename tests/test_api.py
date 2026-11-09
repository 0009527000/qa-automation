"""参数化执行每条用例：请求 → 断言 → 结果（成功/失败都）落库。"""
import time

from common import db
from common.checks import check_case, parse_json


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
        # 断言规则与 runner 通道共用 common/checks.py，避免两边口径不一致
        check_case(case, http_code, resp.text, parse_json(resp.text))

    except Exception as exc:
        status = "failed"
        message = str(exc)
        raise
    finally:
        cost_ms = round((time.perf_counter() - start) * 1000)
        db.save_result(case["id"], status, cost_ms, http_code, message, batch)
