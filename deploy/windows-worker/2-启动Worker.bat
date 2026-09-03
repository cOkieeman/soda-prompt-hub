@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Prompt Hub 5060 Ti Worker

if not exist "worker-config.json" (
  echo [ERROR] worker-config.json not found.
  echo Copy worker-config.example.json to worker-config.json first.
  pause
  exit /b 2
)

python --version
echo Keep this window open while Prompt Hub sends jobs.
echo.
python prompt_hub_worker.py --config worker-config.json
set EXIT_CODE=%ERRORLEVEL%

echo.
echo Worker stopped. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
