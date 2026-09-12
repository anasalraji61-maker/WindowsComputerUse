@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal EnableExtensions

set "ROOT=%CD%"
set "LLAMA_DIR=%ROOT%\APOS\llama_cpp"
set "BIN_DIR=%LLAMA_DIR%\bin"
set "MODEL_DIR=%LLAMA_DIR%\models"
set "MODEL_FILE=%MODEL_DIR%\Qwen2.5-3B-Instruct-Q4_K_M.gguf"
set "SERVER=%BIN_DIR%\llama-server.exe"

echo ========================================
echo  COS — Setup llama.cpp
echo ========================================
mkdir "%BIN_DIR%" 2>nul
mkdir "%MODEL_DIR%" 2>nul

set PYTHONPATH=%ROOT%\APOS
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python "%ROOT%\APOS\tools\setup_llamacpp.py"
if errorlevel 1 (
  echo.
  echo فشل الإعداد التلقائي. راجع الرسائل أعلاه.
  pause
  exit /b 1
)

echo.
echo تم. شغّل الآن: start_llamacpp.bat
echo ثم: check_brain.bat
pause
