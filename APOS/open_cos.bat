@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo COS Personal — starting...
python -m pip install -q -r requirements.txt
set PYTHONPATH=%CD%
python ui\app.py
if errorlevel 1 pause
