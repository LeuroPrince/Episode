@echo off
setlocal

cd /d "%~dp0"

python -c "import flask, fitz, PIL" >nul 2>nul
if errorlevel 1 (
  echo Episode needs Python dependencies before it can start.
  echo.
  echo Please run:
  echo   python -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

start "Episode Server" /D "%~dp0" python app.py

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:7865/"
