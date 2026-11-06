"""极简 YAML 解析器（只用标准库，没有任何第三方依赖）。

设计目的：让 cases/*.yaml 在没有 PyYAML 的 Python 环境里也能被读取。
装了 PyYAML 时 `common/cases.py` 会优先用官方实现，本模块自动退居备用。

支持的语法子集（正好覆盖本项目用例的写法）：
  - 块状 mapping / sequence，靠缩进表达层级
  - 行内 flow mapping  {k: v, k2: v2}
  - 行内 flow sequence [a, b]
  - 标量：带引号字符串、整数、true/false/null、裸字符串
不支持：锚点、多行文本块、注释保留、同层混合类型等高级特性。
"""

_INT = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def loads(text):
    """把 YAML 文本解析成 Python 对象。"""
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        body = raw.rstrip()
        # 行尾注释（只处理不在引号里的 " #"）
        body = _strip_comment(body)
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        lines.append((indent, body.strip()))
    if not lines:
        return None
    value, _ = _parse_node(lines, 0, lines[0][0])
    return value


def _strip_comment(line):
    quote = ""
    for idx, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch == "#" and idx and line[idx - 1] == " ":
            return line[:idx].rstrip()
    return line


def _parse_node(lines, i, indent):
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- "):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    out = {}
    while i < len(lines) and lines[i][0] == indent:
        text = lines[i][1]
        if text.startswith("- "):
            break
        pair = _split_kv(text)
        if pair is None:
            i += 1
            continue
        key, raw = pair
        i += 1
        if raw == "":
            if i < len(lines) and lines[i][0] > indent:
                out[key], i = _parse_node(lines, i, lines[i][0])
            else:
                out[key] = None
        else:
            out[key] = _value(raw)
    return out, i


def _parse_seq(lines, i, indent):
    out = []
    item_indent = indent + 2
    while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
        rest = lines[i][1][2:].strip()
        if not rest:
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                val, i = _parse_node(lines, i, lines[i][0])
            else:
                val = None
            out.append(val)
            continue
        pair = _split_kv(rest)
        if pair is None:
            out.append(_value(rest))
            i += 1
            continue
        # "- key: value" 形式：后续同缩进的 key 都属于同一个 item
        key, raw = pair
        item = {key: _value(raw) if raw != "" else None}
        i += 1
        while i < len(lines) and lines[i][0] >= item_indent:
            if lines[i][0] == item_indent:
                sub = _split_kv(lines[i][1])
                if sub is None:
                    break
                k, v = sub
                i += 1
                if v == "":
                    if i < len(lines) and lines[i][0] > item_indent:
                        item[k], i = _parse_node(lines, i, lines[i][0])
                    else:
                        item[k] = None
                else:
                    item[k] = _value(v)
            else:
                break
        out.append(item)
    return out, i


def _split_kv(text):
    """把 "key: value" 拆成 (key, value)；不是键值对时返回 None。"""
    depth = 0
    quote = ""
    for idx, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch in "{[":
            depth += 1
            continue
        if ch in "}]":
            depth -= 1
            continue
        if ch == ":" and depth == 0:
            nxt = text[idx + 1] if idx + 1 < len(text) else " "
            if nxt in (" ", "\t") or idx + 1 == len(text):
                return _unquote(text[:idx].strip()), text[idx + 1:].strip()
    return None


def _value(token):
    token = token.strip()
    if token.startswith("{") and token.endswith("}"):
        out = {}
        for part in _split_flow(token[1:-1]):
            pair = _split_kv(part)
            if pair is None:
                continue
            k, v = pair
            out[k] = _value(v) if v != "" else ""
        return out
    if token.startswith("[") and token.endswith("]"):
        return [_value(p) for p in _split_flow(token[1:-1])]
    return _scalar(token)


def _split_flow(text):
    parts, buf, depth, quote = [], "", 0, ""
    for ch in text:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf += ch
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def _unquote(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        inner = text[1:-1]
        return inner.replace('\\"', '"').replace("\\'", "'")
    return text


def _scalar(token):
    token = token.strip()
    if not token:
        return ""
    if token[0] in "\"'":
        return _unquote(token)
    low = token.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    if token.lstrip("-").isdigit():
        try:
            return int(token)
        except ValueError:
            pass
    return token
