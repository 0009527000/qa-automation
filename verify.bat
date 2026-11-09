@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title qa-automation - self check

echo ==========================================
echo   qa-automation : one-shot self check
echo   No pip / pytest / third-party packages needed
echo ==========================================
echo.

rem ---- 1. 找一个真正能用的 Python（py / python / python3 依次试） ----
set "PY="
for %%C in (py python python3) do (
  if not defined PY (
    %%C -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=%%C"
  )
)

if not defined PY (
  echo [ERROR] No usable Python 3 found.
  echo.
  echo   1^) Install Python 3.7+ : https://www.python.org/downloads/
  echo      Tick "Add python.exe to PATH" during setup.
  echo   2^) Already installed but still failing? Open a terminal and check
  echo      that "python --version" works there.
  echo.
  if not "%QA_NO_PAUSE%"=="1" pause
  exit /b 1
)

rem ---- 2. 交给 launcher.py：体检 -> 跑用例 + 统计 -> 人话报错 ----
%PY% launcher.py verify %*
set "CODE=%ERRORLEVEL%"

echo.
echo Exit code: %CODE%
if not "%QA_NO_PAUSE%"=="1" (
  echo Window stays open so you can read the result.
  pause
)
exit /b %CODE%
