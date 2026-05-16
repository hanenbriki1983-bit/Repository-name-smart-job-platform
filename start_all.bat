@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=C:\Users\ASUS\smart-job-platform"
set "BACKEND_PORT=8001"
set "FRONTEND_PORT=5173"
set "FRONTEND_FALLBACK_PORT=5174"
set "DEMO_MODE=1"

echo ============================================
echo Smart Job Platform Launcher
echo ROOT: %ROOT%
echo DEMO_MODE: %DEMO_MODE%
echo ============================================

if not exist "%ROOT%\backend\main.py" (
  echo [ERROR] Backend project not found at "%ROOT%\backend".
  pause
  exit /b 1
)
if not exist "%ROOT%\frontend\package.json" (
  echo [ERROR] Frontend project not found at "%ROOT%\frontend".
  pause
  exit /b 1
)
if not exist "C:\Program Files\nodejs\npm.cmd" (
  echo [ERROR] npm not found at "C:\Program Files\nodejs\npm.cmd".
  pause
  exit /b 1
)

call :is_port_in_use %BACKEND_PORT%
if "!PORT_BUSY!"=="1" (
  echo [WARN] Port %BACKEND_PORT% is already in use. Backend might already be running.
) else (
  echo [INFO] Starting backend on port %BACKEND_PORT%...
  start "SmartJob Backend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%ROOT%\backend'; $env:DEMO_MODE='%DEMO_MODE%'; alembic upgrade head; uvicorn main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"
)

call :wait_for_port %BACKEND_PORT% 40
if "!PORT_READY!" NEQ "1" (
  echo [ERROR] Backend failed to start on port %BACKEND_PORT%.
  echo [HINT] Check the "SmartJob Backend" window for Python/alembic errors.
  pause
  exit /b 1
)
echo [OK] Backend is running on http://127.0.0.1:%BACKEND_PORT%/

call :is_port_in_use %FRONTEND_PORT%
if "!PORT_BUSY!"=="1" (
  echo [WARN] Port %FRONTEND_PORT% is already in use. Starting frontend on fallback port %FRONTEND_FALLBACK_PORT%.
  start "SmartJob Frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%ROOT%\frontend'; & 'C:\Program Files\nodejs\npm.cmd' run dev -- --host 127.0.0.1 --port %FRONTEND_FALLBACK_PORT%"
  set "OPEN_PORT=%FRONTEND_FALLBACK_PORT%"
) else (
  echo [INFO] Starting frontend on port %FRONTEND_PORT%...
  start "SmartJob Frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%ROOT%\frontend'; & 'C:\Program Files\nodejs\npm.cmd' run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"
  set "OPEN_PORT=%FRONTEND_PORT%"
)

call :wait_for_port !OPEN_PORT! 40
if "!PORT_READY!" NEQ "1" (
  echo [ERROR] Frontend failed to start on port !OPEN_PORT!.
  echo [HINT] Check the "SmartJob Frontend" window for npm/vite errors.
  pause
  exit /b 1
)

echo [OK] Frontend is running on http://127.0.0.1:!OPEN_PORT!/
echo [INFO] Opening browser...
start "" "http://127.0.0.1:!OPEN_PORT!/"
echo [DONE] App is ready for presentation.
echo Demo Login: demo@smartjob.local / demo1234
exit /b 0

:is_port_in_use
set "PORT_BUSY=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING"') do (
  set "PORT_BUSY=1"
)
exit /b

:wait_for_port
set "PORT_READY=0"
set "target_port=%~1"
set "max_tries=%~2"
if "%max_tries%"=="" set "max_tries=30"
for /L %%i in (1,1,%max_tries%) do (
  call :is_port_in_use %target_port%
  if "!PORT_BUSY!"=="1" (
    set "PORT_READY=1"
    goto :eof
  )
  timeout /t 1 /nobreak >nul
)
exit /b
