@echo off
setlocal

set ROOT=C:\Users\ASUS\smart-job-platform
cd /d %ROOT%\frontend

"C:\Program Files\nodejs\npm.cmd" run dev -- --host 127.0.0.1 --port 5173

endlocal
