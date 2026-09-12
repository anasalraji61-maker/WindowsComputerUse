@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo  COS — Setup Whisper STT
echo ========================================
python "%~dp0APOS\tools\setup_whisper.py"
if errorlevel 1 (
  echo Failed.
  pause
  exit /b 1
)
echo.
echo Done. Restart open_system.bat
pause
