@echo off
cd /d "%~dp0"
echo Installing optional intelligence router...
where npm >nul 2>&1 || (echo Node.js/npm is required.& pause & exit /b 1)
npm install --no-audit --no-fund
if errorlevel 1 (echo Installation failed.& pause& exit /b 1)
echo Done. Add PUTER_ENABLED=true and PUTER_AUTH_TOKEN to .env.
pause
