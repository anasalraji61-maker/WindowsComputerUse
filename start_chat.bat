@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo   Windows Computer Use - CHAT MODE
echo ========================================
echo Type your task, then Enter.
echo Type exit to quit.
echo Emergency stop: mouse to TOP-LEFT corner
echo.
python agent.py --chat
pause
