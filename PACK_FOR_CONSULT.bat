@echo off
chcp 65001 >nul
title Rebuild consultation ZIP
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CONSULTATION_PACK\make_zip.ps1"
pause
