@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ELDEN AI - All Services

if not exist logs mkdir logs
set "LOG=logs\startup.log"
echo.>>"%LOG%"
echo ===== ELDEN AI startup %date% %time% =====>>"%LOG%"

echo [1/8] Checking Python...
where py >nul 2>&1
if not errorlevel 1 (set "PY=py") else (
  where python >nul 2>&1
  if errorlevel 1 goto :no_python
  set "PY=python"
)
%PY% --version >>"%LOG%" 2>&1
if errorlevel 1 goto :failed

if not exist .env (
  echo [SETUP] Starting configuration wizard...
  %PY% setup.py
  if errorlevel 1 goto :failed
)

echo [2/8] Preparing bot environment...
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv >>"%LOG%" 2>&1
  if errorlevel 1 goto :failed
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo [3/8] Installing/checking bot packages...
python -m pip install --disable-pip-version-check -r requirements.txt >>"%LOG%" 2>&1
if errorlevel 1 goto :failed

echo [4/8] Checking Python 3.11 for OpenAI Whisper...
py -3.11 -c "import sys; print(sys.version)" >>"%LOG%" 2>&1
if errorlevel 1 goto :no_python311
if not exist ".venv-whisper\Scripts\python.exe" (
  py -3.11 -m venv .venv-whisper >>"%LOG%" 2>&1
  if errorlevel 1 goto :failed
)

echo [5/8] Installing/checking OpenAI Whisper...
".venv-whisper\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-whisper.txt >>"%LOG%" 2>&1
if errorlevel 1 goto :failed

echo [6/8] Checking configuration...
python -c "from app.config import settings; print('Configuration OK')" >>"%LOG%" 2>&1
if errorlevel 1 goto :bad_config

echo [7/8] Running startup checks...
python preflight.py
if errorlevel 1 goto :failed

echo [8/8] Starting all services...
echo Only this main ELDEN AI terminal stays visible when HIDE_SERVICE_WINDOWS=true.
echo Hidden service logs are saved under logs\services.
python launcher.py
if errorlevel 1 goto :runtime_failed
goto :end

:no_python
echo [ERROR] Python was not found.
goto :pause_error

:no_python311
echo.
echo [ERROR] OpenAI Whisper requires Python 3.11 for this project.
echo Install Python 3.11 from python.org with Python Launcher enabled.
echo Keep Python 3.13 installed; both versions can coexist.
goto :pause_error

:bad_config
echo [ERROR] The .env configuration is incomplete or invalid.
goto :show_startup_log

:runtime_failed
echo [ERROR] ELDEN AI stopped unexpectedly. See logs\runtime.log
goto :pause_error

:failed
echo [ERROR] Startup failed. See %LOG%
:show_startup_log
type "%LOG%"
:pause_error
pause
exit /b 1

:end
echo ELDEN AI stopped normally.
pause
