@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   COS Brain Setup — Ollama (مجاني محلي)
echo ========================================
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama غير موجود في PATH.
  echo حمّله من: https://ollama.com/download
  echo بعد التثبيت أعد تشغيل هذا الملف.
  pause
  exit /b 1
)

echo تشغيل خدمة Ollama إن لزم...
start "" /min ollama serve
timeout /t 2 >nul

set MODEL=%COS_OLLAMA_MODEL%
if "%MODEL%"=="" set MODEL=qwen2.5:7b
echo سحب النموذج: %MODEL%
ollama pull %MODEL%

echo.
echo فحص من Python...
set PYTHONPATH=%CD%\APOS
python -c "from cos.brain import status_text; print(status_text())"
echo.
echo تم. اكتب في الواجهة: حالة العقل
pause
