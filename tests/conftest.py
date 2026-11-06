"""加载 YAML 用例、初始化结果库、注入 HTTP client，并按用例 tags 打 pytest 标记。"""
from pathlib import Path

import pytest
import yaml

from common import db
from common.config import API_TOKEN, BASE_URL
from common.http_client import ApiClient

ROOT = Path(__file__).resolve().parents[1]


def load_cases():
    cases = []
    for path in sorted((ROOT / "cases").glob("*.yaml")):
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for case in data.get("cases", []):
            case["module"] = path.stem
            cases.append(case)
    return cases


CASES = load_cases()


@pytest.fixture(scope="session", autouse=True)
def init_database():
    db.init_db()


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
