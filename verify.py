"""One-shot self check for this repository.

Windows: double-click verify.bat
Or run:  python verify.py

It starts the mock server, runs the suite, checks the result table,
then cleans up. No two-terminal setup needed.
"""
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
DB = os.path.join(ROOT, "qa_results.sqlite3")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


def ensure_deps():
    need = []
    for mod, pkg in (("pytest", "pytest"), ("requests", "requests"), ("yaml", "PyYAML")):
        if importlib.util.find_spec(mod) is None:
            need.append(pkg)
    if need:
        print("[1/5] Installing:", ", ".join(need))
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + need)
        if r.returncode:
            print("FAIL: pip install failed")
            return False
    else:
        print("[1/5] Dependencies OK")
    return True


def main():
    if os.path.exists(DB):
        os.remove(DB)
    if not ensure_deps():
        return 1

    print("[2/5] Starting mock server ...")
    srv = subprocess.Popen(
        [sys.executable, "mock_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.2)
    try:
        print("[3/5] Running all cases ...")
        run = subprocess.run([sys.executable, "-m", "pytest", "-q"])
        smoke = subprocess.run(
            [sys.executable, "-m", "pytest", "-m", "smoke", "--collect-only", "-q"],
            capture_output=True,
            text=True,
        )
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv.kill()

    smoke_n = 0
    for line in smoke.stdout.splitlines():
        m = re.search(r":\s*(\d+)\s*$", line.strip())
        if m:
            smoke_n = int(m.group(1))

    print("[4/5] Checking run_result table ...")
    rows, cases = [], 0
    if os.path.exists(DB):
        conn = sqlite3.connect(DB)
        rows = conn.execute(
            "select status, count(*) from run_result group by status"
        ).fetchall()
        cases = conn.execute(
            "select count(distinct case_id) from run_result"
        ).fetchone()[0]
        conn.close()

    print("      cases executed :", cases)
    print("      results        :", rows)
    print("      smoke selected :", smoke_n)

    ok = (
        run.returncode == 0
        and rows == [("passed", 12)]
        and cases == 12
        and smoke_n == 3
    )

    print("[5/5] Cleaning up generated files ...")
    if os.path.exists(DB):
        os.remove(DB)
    shutil.rmtree(os.path.join(ROOT, ".pytest_cache"), ignore_errors=True)

    print()
    print("RESULT:", "PASS - everything works" if ok else "FAIL - see messages above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
