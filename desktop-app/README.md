# Speech Translator — Desktop App (EXE, BYOK)

Aplikasi desktop Windows mandiri untuk speech-to-speech translation (mic + system audio).
Menggunakan **Bring-Your-Own-Key (BYOK)**: user memakai **kunci API AI-nya sendiri**
(Groq untuk STT & NMT, Gemini opsional untuk NMT, Edge-TTS untuk suara) — biaya AI
dibebankan ke akun user, bukan ke operator server.

Tidak perlu install Python, tidak perlu server lokal. Satu file `.exe`.

## Cara pakai (user)
1. Klik dua kali `SpeechTranslator.exe`.
2. Pilih **Mikrofon**, **System audio (lawan bicara)**, **Output suara terjemahan**, bahasa.
3. Isi **Groq API Key** (dan opsional **Gemini API Key**).
4. Klik **Start** — subtitle + suara terjemahan muncul real-time.

> Groq key: https://console.groq.com/keys · Gemini key (opsional): https://aistudio.google.com/apikey

## Cara build EXE (developer, Windows)
```bat
cd desktop-app
build_app.bat
```
Hasil: `desktop-app/dist/SpeechTranslator.exe` (~37 MB).

Build memakai venv bersih (`build_venv/`) agar EXE **tidak** menyertakan
torch/faster-whisper/piper — semua AI via cloud (BYOK).

## Arsitektur
```
desktop_app.py  (GUI tkinter + capture soundcard + pipeline)
   ├─ pipeline/stt.py             → Groq Whisper (BYOK)
   ├─ pipeline/nmt.py             → Groq Llama / Gemini (BYOK)
   └─ pipeline/edge_tts_engine.py → Microsoft Edge-TTS (neural voice)
```
Capture mic + system loopback via `soundcard`, buffering + VAD energi, flush pada
jeda diam/maks buffer, lalu STT→NMT→TTS.

## Catatan keamanan
- Kunci API hanya di memori aplikasi (tidak disimpan ke disk).
- Tanpa kunci Groq, aplikasi menolak Start (fail-closed).
