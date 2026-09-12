@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Warm Whisper medium model (more accurate Arabic, slower)...
set COS_WHISPER_MODEL=medium
python APOS\tools\setup_whisper.py
if errorlevel 1 (
  pause
  exit /b 1
)
echo.
echo Tip: set COS_WHISPER_MODEL=medium in APOS\.env
pause
