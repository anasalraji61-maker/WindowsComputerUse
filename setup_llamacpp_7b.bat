@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Downloading Qwen2.5-7B Q4_K_M for stronger local brain (~4.7GB)...
echo Keep this window open until finished.
set COS_LLAMA_SIZE=7b
python APOS\tools\setup_llamacpp.py
if errorlevel 1 (
  echo Setup failed.
  pause
  exit /b 1
)
echo.
echo Done. Close any running llama-server, then run start_llamacpp.bat
echo It will prefer the 7B model automatically.
pause
