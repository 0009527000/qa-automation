@echo off
cd /d "%~dp0"
echo ==========================================
echo   qa-automation : one-shot self check
echo ==========================================
echo.
python verify.py
echo.
echo Window stays open so you can read the result.
pause
