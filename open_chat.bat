@echo off
chcp 65001 >nul
cd /d "%~dp0"
python chat_ui.py
if errorlevel 1 (
  echo.
  echo ERROR - window failed to open
  echo Check agent_run.log
  pause
)
