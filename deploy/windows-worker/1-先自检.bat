@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Prompt Hub 5060 Ti Worker - Self Test

if not exist "worker-config.json" (
  echo [ERROR] worker-config.json not found.
  echo Copy worker-config.example.json to worker-config.json first.
  pause
  exit /b 2
)

python --version
python prompt_hub_worker.py --config worker-config.json --self-test
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo [OK] Worker and local ComfyUI are ready.
) else (
  echo [ERROR] Self test failed. Exit code: %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%
