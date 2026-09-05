@echo off
setlocal
cd /d "%~dp0"
title ELDEN AI Setup
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
%PY% setup.py
if errorlevel 1 (
  echo.
  echo Setup failed. Check that Python 3.11 or newer is installed.
)
echo.
pause
