@echo off
setlocal
cd /d "%~dp0"

call "venv\Scripts\activate.bat"

python --version
python -c "import flask; print('Flask OK')"
python -c "import psycopg; print('psycopg OK')"

REM Load .env using python-dotenv and verify it is present
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('DATABASE_URL set?', bool(os.getenv('DATABASE_URL'))); print(os.getenv('DATABASE_URL'))"

REM Test DB connection using dotenv-loaded env var
python -c "from dotenv import load_dotenv; load_dotenv(); import os, psycopg; psycopg.connect(os.environ['DATABASE_URL']).close(); print('DB connection OK')"
if errorlevel 1 (
  echo [ERROR] DB connection failed. Check DATABASE_URL value.
  pause
  exit /b 1
)

python app.py
pause