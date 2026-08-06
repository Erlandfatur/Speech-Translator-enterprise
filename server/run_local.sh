#!/usr/bin/env bash
# Run the Speech Translator server locally
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "[setup] Creating venv..."
  python -m venv venv
fi
# shellcheck disable=SC1091
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

echo "[run] Starting Speech Translator server..."
echo "[run] http://localhost:8000  |  ws://localhost:8000/ws/translate"
python main.py
