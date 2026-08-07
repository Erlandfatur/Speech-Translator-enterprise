# Build a self-contained Windows EXE for the Speech Translator desktop app (BYOK).
# Usage:  build_app.bat
@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Installing build + runtime deps...
pip install -r requirements-app.txt pyinstaller || goto :error

echo [2/3] Building EXE with PyInstaller...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SpeechTranslator ^
  --paths . --paths ..\server ^
  --hidden-import soundcard ^
  --hidden-import soundfile ^
  --hidden-import edge_tts ^
  --hidden-import groq ^
  --hidden-import google.genai ^
  --hidden-import pipeline.stt ^
  --hidden-import pipeline.nmt ^
  --hidden-import pipeline.edge_tts_engine ^
  desktop_app.py || goto :error

echo.
echo Build selesai: dist\SpeechTranslator.exe
goto :eof

:error
echo.
echo Build GAGAL. Periksa pesan error di atas.
exit /b 1
