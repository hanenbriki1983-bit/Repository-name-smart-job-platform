@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at venv\Scripts\python.exe
  echo Create it first, then install dependencies.
  pause
  exit /b 1
)

echo Starting Streamlit chatbot on http://127.0.0.1:8502
start "" "http://127.0.0.1:8502"
venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true

echo.
echo Streamlit exited.
pause
