@echo off
cd /d "%~dp0"
echo ======================================
echo        AUCTION.N - STARTUP
echo ======================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer from python.org.
  pause
  exit /b 1
)
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
pause
