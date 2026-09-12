@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal EnableDelayedExpansion

set "LLAMA_DIR=%CD%\APOS\llama_cpp"
set "BIN_DIR=%LLAMA_DIR%\bin"
set "MODEL_DIR=%LLAMA_DIR%\models"
set "SERVER=%BIN_DIR%\llama-server.exe"
set "PICKER=%CD%\APOS\tools\pick_llamacpp_model.ps1"

if not exist "%SERVER%" (
  echo llama-server.exe missing. Run setup_llamacpp.bat first.
  pause
  exit /b 1
)

REM Prefer stable 3B by default (7B download was often corrupt after resume)
if not defined COS_LLAMA_PREFER set "COS_LLAMA_PREFER=3b"

set "MODEL="
for /f "usebackq delims=" %%M in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%PICKER%" -ModelDir "%MODEL_DIR%"`) do (
  set "MODEL=%%M"
)

if not defined MODEL (
  echo No complete .gguf model in %MODEL_DIR%
  echo Run setup_llamacpp.bat ^(3B^).
  pause
  exit /b 1
)

echo Starting llama.cpp server...
echo Model: !MODEL!
echo Prefer: %COS_LLAMA_PREFER%
echo API:   http://127.0.0.1:8080
echo Keep this window open while using COS.
echo Tip: headphones + short clear Arabic sentences.
echo.
REM chatml = قالب Qwen الصحيح؛ يمنع ردود الرموز العشوائية غالباً
"%SERVER%" -m "!MODEL!" -c 4096 -ngl 99 --host 127.0.0.1 --port 8080 --jinja --chat-template chatml
pause
