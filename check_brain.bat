@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=%CD%\APOS
python -c "from cos.brain import status_text; from cos.brain import llm; print(status_text()); r=llm.chat('جاوب بكلمة واحدة فقط: جاهز','اختبار اتصال'); print('provider=', r.provider, 'ok=', r.ok, 'text=', (r.text or r.error)[:120])"
pause
