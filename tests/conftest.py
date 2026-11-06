"""pytest 入口：加载 YAML 用例、初始化库、注入 client、按 tags 打标记。

用例读取与 runner.py 共用 common/cases.py，保证两边跑的是同一批用例。
"""
from datetime import datetime

import pytest

from common import cases as case_loader
from common import db
from common.config import API_TOKEN, BASE_URL
from common.http_client import ApiClient

CASES = case_loader.load_cases()


@pytest.fixture(scope="session", autouse=True)
def init_database():
    db.init_db()
    db.sync_cases(CASES)


@pytest.fixture(scope="session")
def batch():
    """一轮测试共用一个批次号，便于统计「最近一次执行」的完整结果。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@pytest.fixture(scope="session")
def client():
    api = ApiClient(BASE_URL, token=API_TOKEN)
    yield api
    api.close()


@pytest.fixture(params=CASES, ids=[c["id"] for c in CASES])
def case(request):
    return request.param


def pytest_collection_modifyitems(items):
    """让 `pytest -m smoke` / `pytest -m regression` 能按 YAML 里的 tags 筛选用例。"""
    by_id = {c["id"]: c for c in CASES}
    for item in items:
        callspec = getattr(item, "callspec", None)
        case_id = callspec.id if callspec else ""
        for tag in by_id.get(case_id, {}).get("tags", []):
            item.add_marker(getattr(pytest.mark, tag))
