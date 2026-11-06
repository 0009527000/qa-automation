"""用例加载：读 cases/*.yaml，装 PyYAML 就用它，没装就用内置 miniyaml。

对外只暴露 load_cases()，runner.py / tests/conftest.py 共用同一份实现，
保证「零依赖跑」和「pytest 跑」读到的是同一批用例。
"""
from pathlib import Path

from common import miniyaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("id", "method", "path", "expect")


def _parse(text):
    try:
        import yaml  # 有就用官方实现，解析更严格
    except ImportError:
        return miniyaml.loads(text)
    return yaml.safe_load(text)


def load_cases(root=None):
    """返回用例列表，每条用例补上 module 字段（取 YAML 文件名）。"""
    base = Path(root) if root else ROOT
    cases = []
    for path in sorted((base / "cases").glob("*.yaml")):
        data = _parse(path.read_text(encoding="utf-8")) or {}
        for index, case in enumerate(data.get("cases") or [], start=1):
            missing = [k for k in REQUIRED if k not in case]
            if missing:
                raise ValueError(
                    "%s 第 %d 条用例缺少字段 %s，请检查 YAML 格式"
                    % (path.name, index, "、".join(missing))
                )
            case.setdefault("name", "")
            case.setdefault("tags", [])
            case["module"] = _module_of(case["id"], path.stem)
            cases.append(case)
    return cases


def _module_of(case_id, stem):
    """模块名优先取用例编号前缀（TC_LOGIN_001 → login），保证统计口径稳定。"""
    parts = str(case_id).split("_")
    if len(parts) >= 3 and parts[0].upper() == "TC" and parts[1]:
        return parts[1].lower()
    return stem


def filter_by_tag(cases, tag):
    if not tag:
        return list(cases)
    return [c for c in cases if tag in (c.get("tags") or [])]
