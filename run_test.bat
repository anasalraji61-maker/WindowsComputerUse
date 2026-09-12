@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running test task in English...
python agent.py "Open Notepad and type Hello from the agent"
pause
