@echo off
cd /d "%~dp0"
echo ==========================================
echo   qa-automation : one-shot self check
echo   No pip / pytest / third-party packages needed
echo ==========================================
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found in PATH.
  echo Install Python 3 and tick "Add python.exe to PATH" during setup.
  pause
  exit /b 1
)
python verify.py
echo.
echo Window stays open so you can read the result.
pause
