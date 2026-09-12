@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   COS Unified System v0.5 FULL
echo ========================================
python -m pip install -q -r APOS\requirements.txt
python -m pip install -q -r requirements.txt
set PYTHONPATH=%CD%\APOS
python APOS\ui\app.py
if errorlevel 1 pause
