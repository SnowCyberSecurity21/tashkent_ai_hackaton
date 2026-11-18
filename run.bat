@echo off
REM Mezon: starts the server on port 8000 (installs nothing). First run: pip install -r requirements.txt
cd /d "%~dp0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 %*
