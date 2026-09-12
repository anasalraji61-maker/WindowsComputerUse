@echo off
chcp 65001 >nul
title COS — QuantConnect Backtest Executor
cd /d "%~dp0APOS"
echo.
echo  ============================================
echo   COS QC Executor — direct API backtest
echo   No mouse. No browser paste.
echo  ============================================
echo.
python -c "from cos.execution.qc_executor import run_backtest_text; print(run_backtest_text())"
echo.
echo  Done. Report folder: APOS\data\reports
pause
