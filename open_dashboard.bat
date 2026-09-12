@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo COS Dashboard...
set PYTHONPATH=%CD%\APOS
python APOS\ui\dashboard.py
if errorlevel 1 pause
