@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting COS Remote for phone...
set PYTHONPATH=%CD%\APOS
python APOS\ui\remote_server.py
if errorlevel 1 pause
