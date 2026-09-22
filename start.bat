@echo off
setlocal
cd /d "%~dp0"
if /i "%~1"=="--help" goto help
if not "%~1"=="" if /i not "%~1"=="--check" if /i not "%~1"=="--sandbox" if /i not "%~1"=="--demo" if /i not "%~1"=="--test" goto help
where uv >nul 2>nul
if errorlevel 1 (
  echo Install uv first: https://docs.astral.sh/uv/getting-started/installation/
  goto failed
)
where node >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 22 or newer with npm, then reopen this terminal.
  goto failed
)
where npm.cmd >nul 2>nul
if errorlevel 1 goto failed
if /i "%~1"=="--check" (
  if not exist "backend\.venv\Scripts\python.exe" (
    echo Backend dependencies are missing. Run start.bat or start.bat --sandbox first.
    exit /b 1
  )
  "backend\.venv\Scripts\python.exe" scripts\dev.py --check
  exit /b
)
echo Installing locked dependencies...
pushd backend
uv sync --frozen
if errorlevel 1 (
  popd
  goto failed
)
popd
pushd frontend
call npm.cmd ci --no-audit --no-fund
if errorlevel 1 (
  popd
  goto failed
)
popd
if /i "%~1"=="--test" goto tests
"backend\.venv\Scripts\python.exe" scripts\dev.py %1
if errorlevel 1 goto failed
exit /b 0
:tests
pushd backend
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
  popd
  goto failed
)
popd
pushd frontend
call npm.cmd run build
if errorlevel 1 goto testsfailed
call npx.cmd playwright install chromium
if errorlevel 1 goto testsfailed
call npx.cmd playwright test --config playwright.personal.config.js
if errorlevel 1 goto testsfailed
call npx.cmd playwright test --workers=2
if errorlevel 1 goto testsfailed
popd
echo All checks passed.
exit /b 0
:testsfailed
popd
:failed
echo.
echo Orbit could not complete this command. Check the error above and README.md.
pause
exit /b 1
:help
echo start.bat             Install dependencies, migrate configured PostgreSQL, and start Orbit.
echo start.bat --sandbox   Start with a disposable local database; no .env or API keys needed.
echo start.bat --demo      Open a preloaded local demo, including reference marks and offline assistant.
echo start.bat --check     Read-only dependency/configuration check; no servers or migrations.
echo start.bat --test      Install dependencies and run backend, build, and browser checks.
exit /b 0
