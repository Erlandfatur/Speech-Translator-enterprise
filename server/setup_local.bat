@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Speech Translator - Local Setup (Windows)
echo ============================================

REM ---- 1. Python check ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ and add to PATH.
    pause
    exit /b 1
)

REM ---- 2. venv ----
if not exist "venv\Scripts\activate.bat" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat

REM ---- 3. Install deps ----
echo [2/4] Installing dependencies (first time may take a while)...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

REM ---- 4. .env ----
if not exist ".env" (
    echo [3/4] Creating .env from example...
    copy ".env.example" ".env"
    echo  NOTE: Edit server\.env and fill in GROQ_API_KEY & GEMINI_API_KEY
) else (
    echo [3/4] .env already exists.
)

echo [4/4] Setup complete.
echo.
echo To run:  python main.py
echo Server:  http://localhost:8000  |  WS: ws://localhost:8000/ws/translate
echo.
pause
