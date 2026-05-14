@echo off
setlocal

set ROOT=C:\Users\ASUS\smart-job-platform

start "SmartJob Backend" powershell -NoExit -ExecutionPolicy Bypass -Command "cd /d %ROOT%\backend; alembic upgrade head; uvicorn main:app --reload --port 8001"
start "SmartJob Frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "cd /d %ROOT%\frontend; & 'C:\Program Files\nodejs\npm.cmd' run dev"

endlocal
