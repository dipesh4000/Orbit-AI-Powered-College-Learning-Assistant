@echo off

start "Backend" cmd /k "cd /d %~dp0backend && uv run uvicorn orbit.main:app --reload"

start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"