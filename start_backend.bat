@echo off
setlocal

set ROOT=C:\Users\ASUS\smart-job-platform
cd /d %ROOT%\backend

if exist "%ROOT%\venv\Scripts\python.exe" (
  "%ROOT%\venv\Scripts\python.exe" -m alembic upgrade head
  "%ROOT%\venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8001
) else (
  echo venv python not found at %ROOT%\venv\Scripts\python.exe
  echo Run backend manually from your active environment.
  pause
)

endlocal
