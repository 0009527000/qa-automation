"""Zero-dependency self check for this repository.

Works on ANY Python 3.x - no pip, no pytest, no third-party packages required.
Windows: double-click verify.bat
Or run:  python verify.py   (also works via VS Code "Run Python File")

It starts the bundled mock server, exercises the core API scenarios using only
the standard library, writes results into the same SQLite table as the real
framework, and prints PASS / FAIL. When pytest + requests + PyYAML happen to be
installed in the current interpreter, it additionally runs the full 12-case suite.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from common import db  # noqa: E402  (stdlib-only module: sqlite3 + config)

DB = db.config.DB_PATH
BASE = "http://127.0.0.1:8000"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Core scenarios mirroring cases/*.yaml, expressed without any third-party package.
CHECKS = [
    {"id": "TC_LOGIN_001", "method": "POST", "path": "/api/login",
     "body": {"username": "test01", "password": "123456"}, "token": True,
     "status": 200, "json": {"code": 0}},
    {"id": "TC_LOGIN_002", "method": "POST", "path": "/api/login",
     "body": {"username": "test01", "password": ""}, "token": True,
     "status": 400, "json": {"code": 1001}},
    {"id": "TC_LOGIN_003", "method": "POST", "path": "/api/login",
     "body": {"username": "test01", "password": "wrong"}, "token": True,
     "status": 401, "json": {"code": 1002}},
    {"id": "TC_QUERY_001", "method": "GET", "path": "/api/query",
     "params": {"keyword": "软件"}, "token": True,
     "status": 200, "json": {"code": 0}},
    {"id": "TC_ORDER_001", "method": "POST", "path": "/api/order",
     "body": {"itemId": 1, "quantity": 2}, "token": True,
     "status": 200, "json": {"code": 0}},
    {"id": "TC_ORDER_004", "method": "POST", "path": "/api/order",
     "body": {"itemId": 1, "quantity": 1}, "token": False,
     "status": 401, "json": {"code": 1004}},
]


def call(item):
    url = BASE + item["path"]
    if item.get("params"):
        url += "?" + urllib.parse.urlencode(item["params"])
    data = None
    if item.get("body") is not None:
        data = json.dumps(item["body"]).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=item["method"])
    req.add_header("Content-Type", "application/json")
    if item.get("token", True):
        req.add_header("X-Token", "demo-token")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        payload = {}
    return status, payload


def read_db():
    conn = db.connect()[0]
    try:
        rows = conn.execute(
            "select status, count(*) from run_result group by status"
        ).fetchall()
        cases = conn.execute(
            "select count(distinct case_id) from run_result"
        ).fetchone()[0]
        return rows, cases
    finally:
        conn.close()


def core_checks():
    db.init_db()
    ok = True
    for item in CHECKS:
        start = time.perf_counter()
        try:
            status, payload = call(item)
            cost = round((time.perf_counter() - start) * 1000)
            assert status == item["status"], "expected HTTP %s, got %s" % (item["status"], status)
            for key, value in item["json"].items():
                assert payload.get(key) == value, "field %s: expected %r, got %r" % (
                    key, value, payload.get(key))
            db.save_result(item["id"], "passed", cost, status)
            print("      %-14s OK   HTTP %s" % (item["id"], status))
        except Exception as exc:
            ok = False
            db.save_result(item["id"], "failed", 0, 0, str(exc))
            print("      %-14s FAIL %s" % (item["id"], exc))
    rows, cases = read_db()
    print("      DB: %s rows, %s" % (cases, rows))
    return ok and rows == [("passed", len(CHECKS))] and cases == len(CHECKS)


def full_suite_available():
    return all(importlib.util.find_spec(m) is not None
               for m in ("pytest", "requests", "yaml"))


def main():
    print("=" * 52)
    print(" qa-automation self check")
    print(" Python %s" % sys.version.split()[0])
    print("=" * 52)

    for path in (os.path.abspath(DB),):
        if os.path.exists(path):
            os.remove(path)

    print("[1/4] No third-party packages required for the core check.")
    print("[2/4] Starting mock server ...")
    srv = subprocess.Popen(
        [sys.executable, "mock_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.2)
    ok_core = False
    ok_full = None
    full_rows = None
    try:
        print("[3/4] Core API checks (standard library only) ...")
        ok_core = core_checks()

        # reset DB so the pytest suite writes a clean set of 12 results
        if os.path.exists(os.path.abspath(DB)):
            os.remove(os.path.abspath(DB))

        print("[4/4] Full pytest suite:", end=" ")
        if full_suite_available():
            print("running ...")
            r = subprocess.run([sys.executable, "-m", "pytest", "-q"])
            rows, cases = read_db()
            full_rows = rows
            ok_full = r.returncode == 0 and rows == [("passed", 12)] and cases == 12
            print("      DB: %s rows, %s" % (cases, rows))
        else:
            print("SKIPPED")
            print("      (pytest / requests / PyYAML not installed in THIS Python;")
            print("       core check above still validates the full request->assert->DB chain)")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv.kill()

    if os.path.exists(os.path.abspath(DB)):
        os.remove(os.path.abspath(DB))
    shutil.rmtree(os.path.join(ROOT, ".pytest_cache"), ignore_errors=True)

    ok = ok_core and (ok_full is not False)
    print()
    if ok:
        detail = "core checks + full 12-case suite" if ok_full else "core checks (zero dependency)"
        print("RESULT: PASS - everything works [%s]" % detail)
    else:
        print("RESULT: FAIL - see messages above")
        if not ok_core:
            print("        core checks failed: is the mock server reachable on 8000?")
        if ok_full is False:
            print("        pytest suite failed, rows =", full_rows)
    print("=" * 52)
    # Deliberately no sys.exit(): VS Code debugger shows SystemExit as an exception.
    return ok


if __name__ == "__main__":
    main()
