# -*- coding: utf-8 -*-
"""一键启动器：让这个项目在任何入口都能跑起来。

为什么要多这一层？
  Windows 上最常见的三种「跑不起来」，都不是代码问题：
    1. 找不到 Python（PATH 没配 / 只装了 Microsoft Store 的占位 python）
    2. 控制台用 GBK，中文一打印就 UnicodeEncodeError
    3. 8000 端口被别的程序占了，mock_server 起不来，报错又看不懂
  这里统一兜住：先自检、给出人话提示，再调用真正的脚本。

用法：
    python launcher.py            # 等于 run，跑全部用例
    python launcher.py run --tag smoke
    python launcher.py verify     # 一键自检
    python launcher.py report     # 历史统计
    python launcher.py bugs       # 缺陷台账
    python launcher.py check      # 只做环境体检，不跑用例
"""
import json
import os
import socket
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

BAR = "=" * 62
MIN_PY = (3, 7)

# Windows 控制台默认 GBK，中文输出会炸；能改就改成 utf-8，改不了就降级替换
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _say(msg=""):
    print(msg)
    sys.stdout.flush()


def _head(title):
    _say(BAR)
    _say(" qa-automation · %s" % title)
    _say(" Python %s   %s" % (sys.version.split()[0], sys.executable))
    _say(BAR)


def _port_open(host, port, timeout=0.6):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _is_our_mock(base):
    """端口上跑的是不是本项目的 mock_server，而不是别的程序。"""
    try:
        with urllib.request.urlopen(base + "/api/query?keyword=Python", timeout=1.5) as resp:
            body = resp.read().decode("utf-8", "replace")
        payload = json.loads(body)
        # mock 的查询接口固定返回 {"code": 0, "data": [...], "total": n}
        return resp.status == 200 and isinstance(payload.get("data"), list) and "total" in payload
    except Exception:
        return False


def check(verbose=True):
    """返回 (是否可运行, 问题列表)。不跑用例，只体检。"""
    problems = []
    tips = []

    if sys.version_info < MIN_PY:
        problems.append("Python 版本过低：当前 %s，需要 %s 以上" % (
            sys.version.split()[0], ".".join(map(str, MIN_PY))))

    missing = [f for f in ("runner.py", "report.py", "verify.py", "mock_server.py",
                           "cases", "common")
               if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        problems.append("缺少文件/目录：%s（请确认是在 qa-automation 根目录里运行）" % "、".join(missing))

    # 中文字符串能不能输出，决定你会不会看到一堆 UnicodeEncodeError
    try:
        "中文编码测试".encode(sys.stdout.encoding or "utf-8")
    except Exception:
        tips.append("当前控制台编码是 %s，中文可能显示为乱码；run.bat 已自动切到 UTF-8" % (sys.stdout.encoding,))

    from common.config import BASE_URL  # 放在函数里，避免导入期就报错

    host, port = "127.0.0.1", 8000
    try:
        from urllib.parse import urlparse
        parsed = urlparse(BASE_URL)
        host = parsed.hostname or host
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except Exception:
        pass

    explicit_base = bool(os.getenv("BASE_URL"))
    port_busy = _port_open(host, port)
    ours = _is_our_mock(BASE_URL) if port_busy else False
    if port_busy and ours:
        tips.append("检测到 mock 被测服务已在 %s 运行，将直接复用" % BASE_URL)
    elif port_busy and explicit_base:
        tips.append("检测到 %s 已在运行，将直接请求该地址（不会启动 mock）" % BASE_URL)
    elif port_busy:
        problems.append(
            "端口 %s:%s 已被其他程序占用，mock 被测服务起不来（脚本会把这个端口当成业务系统去请求）" % (host, port))
        tips.append("解决：关掉占用该端口的程序；或换个端口 —— 命令行执行 "
                    "set PORT=8010 和 set BASE_URL=http://127.0.0.1:8010 后重跑")
    elif explicit_base:
        problems.append("BASE_URL=%s 连不上：确认被测服务已启动，或清掉该环境变量改用内置 mock" % BASE_URL)

    # 数据库能不能写（只读目录/被占用会在这里暴露）
    try:
        from common import db  # noqa: F401
        db.init_db()
    except Exception as exc:
        problems.append("数据库初始化失败：%s" % exc)
        tips.append("解决：确认当前目录可写，或删掉 qa_results.sqlite3 让它重建")

    if verbose:
        _head("环境体检")
        _say("[Python]  %s" % sys.executable)
        _say("[工作目录] %s" % ROOT)
        _say("[被测地址] %s" % BASE_URL)
        _say("[用例目录] %s 个 YAML" % len([f for f in os.listdir(os.path.join(ROOT, "cases"))
                                             if f.endswith(".yaml")]))
        _say("")
        if problems:
            for item in problems:
                _say("[X] %s" % item)
        else:
            _say("[OK] 环境没问题，可以跑用例")
        for tip in tips:
            _say("[i] %s" % tip)
        _say(BAR)
    return not problems, problems


def _delegate(script, args):
    """用当前解释器去跑真正的脚本，保留退出码与实时输出。"""
    cmd = [sys.executable, script] + list(args)
    try:
        return subprocess.call(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        _say("\n已中断。")
        return 130
    except FileNotFoundError:
        _say("[X] 找不到 %s，确认文件没被删掉" % script)
        return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    action = "run"
    if argv and not argv[0].startswith("-"):
        action = argv.pop(0)

    if action in ("check", "doctor", "env"):
        ok, _ = check()
        return 0 if ok else 2

    table = {
        "run": ("runner.py", "用例执行"),
        "verify": ("verify.py", "一键自检"),
        "report": ("report.py", "历史统计"),
        "html": ("htmlreport.py", "HTML 报告"),
        "bugs": ("buglog.py", "缺陷台账"),
    }
    if action not in table:
        _say("未知命令：%s" % action)
        _say("可用：run / verify / report / html / bugs / check")
        return 2

    script, title = table[action]
    _head(title)

    ok, problems = check(verbose=False)
    if not ok:
        _say("")
        for item in problems:
            _say("[X] %s" % item)
        _say("")
        _say("先解决上面的问题再跑：python launcher.py check 查看完整体检结果")
        return 2

    if action == "run" and not argv:
        _say("没有额外参数，跑全部用例。")
    code = _delegate(script, argv)

    if action == "run" and code != 0:
        _say("")
        _say("退出码 %s：有用例失败或启动异常，看上面第一条 [FAIL] / 报错即可。" % code)
    return code


if __name__ == "__main__":
    sys.exit(main())
