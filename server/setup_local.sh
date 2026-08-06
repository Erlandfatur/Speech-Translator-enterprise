#!/usr/bin/env bash
# Local setup for the Speech Translator server (Git Bash / Linux / macOS)
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo " Speech Translator - Local Setup"
echo "============================================"

# 1. Python check
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] Python not found. Install Python 3.11+."
  exit 1
fi
PY=$(command -v python3 || command -v python)

# 2. venv
if [ ! -d "venv" ]; then
  echo "[1/4] Creating virtual environment..."
  "$PY" -m venv venv
fi
# shellcheck disable=SC1091
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

# 3. Install deps
echo "[2/4] Installing dependencies (first time may take a while)..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. .env
if [ ! -f ".env" ]; then
  echo "[3/4] Creating .env from example..."
  cp .env.example .env
  echo "      NOTE: edit server/.env and fill in GROQ_API_KEY & GEMINI_API_KEY"
else
  echo "[3/4] .env already exists."
fi

echo "[4/4] Setup complete."
echo
echo "To run:  python main.py"
echo "Server:  http://localhost:8000  |  WS: ws://localhost:8000/ws/translate"
