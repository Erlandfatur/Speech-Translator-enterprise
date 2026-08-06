@echo off
setlocal
cd /d "%~dp0"

REM Activate venv if present, else create on the fly
if not exist "venv\Scripts\activate.bat" (
    echo [setup] Creating venv...
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [run] Starting Speech Translator server...
echo [run] http://localhost:8000  |  ws://localhost:8000/ws/translate
python main.py

pause
