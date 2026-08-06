# 🎙️ Speech Translator — AI Speech-to-Speech Live Translator

> 🌍 **Bahasa:** [🇮🇩 Indonesia](README.md) · [🇬🇧 English](README.en.md)

Bidirectional **real-time voice translation & dubbing** for meetings (English ⇄ Indonesian & multi-language). Speech-in → transcribe → translate → natural voice-out, built for Zoom, Teams & Slack workflows.

> 🌐 **Landing Page:** https://erlandfatur.github.io/Speech-Translator-enterprise/ — interaktif, bilingual (EN/ID)

## ✨ Fitur Utama

- **Bidirectional Voice Translation** — 2-way audio pipeline (Audio In → STT → NMT → TTS → Audio Out)
- **Voice Dubbing / Speech-to-Speech** — terjemahan dibacakan dengan suara neural alami
- **Real-time Streaming** — WebSocket duplex, VAD neural, buffer dinamis
- **Speaker Diarization** — menandai pembicara (Pembicara 1, 2, …)
- **Subtitle Overlay** — fallback teks real-time saat latensi tinggi
- **Custom Glossary** — ~370 istilah bisnis/teknis EN⇄ID (98.6% akurasi benchmark)
- **Chrome Extension MV3** — capture mic + tab audio via `tabCapture`

## 🧱 Arsitektur

```
[Chrome Extension (klien)]  --WebSocket-->  [FastAPI Server]
       tabCapture mic+tab                     STT → NMT → TTS
                                              VAD · Diarization · Echo suppression
                                              Virtual Audio (opsional, VB-Cable)
```

### Komponen

| Modul | Stack | Path |
|---|---|---|
| **Server** | FastAPI + WebSocket | `server/` |
| **STT** | Groq Whisper Large v3 Turbo + FasterWhisper fallback | `server/pipeline/stt.py` |
| **NMT** | Groq Llama-3.3-70B + Gemini Flash + Google Translate fallback | `server/pipeline/nmt.py` |
| **TTS** | Edge-TTS (Microsoft Neural) + Piper fallback | `server/pipeline/tts.py` |
| **VAD** | Silero VAD v5 (ONNX) | `server/pipeline/vad.py` |
| **Diarization** | SpeakerDiarizer | `server/pipeline/diarization.py` |
| **Virtual Audio** | VB-Audio Virtual Cable (Windows) / BlackHole (macOS) | `server/pipeline/virtual_mic.py` |
| **Extension** | React + TypeScript + Vite (MV3) | `extension/` |

## 🚀 Menjalankan Server

### Prasyarat
- Python 3.11+
- API keys di `server/.env` (lihat `server/.env.example`)

### Setup
```bash
cd server
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # lalu isi GROQ_API_KEY & GEMINI_API_KEY
```

> **Skrip cepat (lokal):** jalankan `setup_local.bat` lalu `run_local.bat` (Windows), atau `bash setup_local.sh` / `bash run_local.sh` (Git Bash/Linux/macOS). Skrip otomatis buat venv + install deps + buat `.env`.

### Jalankan
```bash
python main.py
```
Server berjalan di `http://localhost:8000`, WebSocket di `ws://localhost:8000/ws/translate`.

> **Auth (opsional):** set `WS_API_TOKEN` di `.env`, lalu klien konek dengan `?token=<value>`. Jika kosong, auth nonaktif (mode dev).

## 🖥️ Menjalankan Extension (Dev)

```bash
cd extension
npm install
npm run dev:ext        # build untuk Chrome extension (watch)
npm run build:ext      # build produksi extension
```
Load folder `extension/dist` di `chrome://extensions` (Developer mode → Load unpacked).

## 🧪 Evaluasi & Test

```bash
cd server
python eval_pipeline.py        # Benchmark akurasi NMT (butuh GROQ/GEMINI key)
python test_full_pipeline.py   # Test pipeline end-to-end
```

### Hasil Benchmark Terkini (Groq Llama-3.3-70B)
- **Akurasi rata-rata:** 98.6%
- **Test lulus (≥90%):** 5/5
- **Latensi NMT rata-rata:** ~468 ms

## ⚙️ Konfigurasi Env

Variabel opsional untuk tuning latensi (`.env.example`):

| Variabel | Default | Keterangan |
|---|---|---|
| `BUFFER_MAX_SEC` | `8.0` | Maks buffer audio (detik) |
| `BUFFER_MIN_SEC` | `1.5` | Min audio sebelum flush (detik) |
| `SILENCE_FLUSH_SEC` | `0.6` | Jeda diam untuk flush |
| `GROQ_COOLDOWN_SEC` | `0.8` | Jeda antar panggilan Groq |
| `BUFFER_TAB_FLUSH_SEC` | `2.0` | Window flush audio tab |
| `ALLOWED_ORIGINS` | localhost | CORS allowlist |
| `WS_API_TOKEN` | *(kosong)* | Auth WebSocket |

## 🚦 CI/CD

- **`.github/workflows/ci.yml`** — lint & build extension (oxlint, tsc, vite) + Python compile smoke test
- **`.github/workflows/pages.yml`** — deploy landing page ke GitHub Pages (folder `docs/`)

## ☁️ Deploy Backend ke Render

Repositori sudah menyertakan `render.yaml` (Blueprint). Langkah:

1. Buka [render.com](https://render.com) → **New** → **Blueprint** → pilih repo ini.
2. Render membaca `render.yaml` → membuat Web Service `speech-translator` dari `server/`.
3. **Set secrets** di service (Settings → Environment):
   `GROQ_API_KEY`, `GEMINI_API_KEY`, `WS_API_TOKEN`.
4. **ALLOWED_ORIGINS** — isi dengan origin landing page/extension (mis. `https://erlandfatur.github.io`).
5. Build & deploy otomatis. URL akan seperti `https://speech-translator.onrender.com`.
   Health check: `https://speech-translator.onrender.com/health` → `{"status":"ok"}`.

> **Catatan:** paket `torch`, `sounddevice`, `piper-tts`, `faster-whisper` cukup berat; pakai plan ber-MEMORY cukup. Jika hanya perlu STT/NMT/TTS via API Groq/Edge, matikan fallback lokal yang berat.

### Alternatif: Fly.io

`server/` juga menyertakan `Dockerfile` & `fly.toml`. Langkah:

1. Install & login [Fly CLI](https://fly.io/docs/flyctl/): `flyctl auth login`.
2. Dari `server/`: `flyctl launch` (ikuti wizard, pakai `fly.toml` yang sudah ada).
3. Set secrets: `flyctl secrets set GROQ_API_KEY=... GEMINI_API_KEY=... WS_API_TOKEN=...`.
4. Deploy: `flyctl deploy`.
5. URL menjadi `https://speech-translator.fly.dev` (health: `/health`).

## 🔒 Keamanan

- API key **hanya di `.env`** (tidak ter-commit — di `.gitignore`)
- CORS allowlist ketat (`ALLOWED_ORIGINS`)
- Auth WebSocket opsional (`WS_API_TOKEN`)
- Config klien di-whitelist (klien tidak bisa inject API key)
- Echo suppression saat TTS playback

## 📄 Dokumentasi Tambahan

- `ANALISIS_PROYEK.md` — analisis proyek & risk assessment lengkap
- `SOKUJI_ALIGNMENT_ROADMAP.md` — roadmap alignment kemampuan
- `AGENTS.md` — aturan proyek & path (anti-typo)
- `deploy/` — template docker-compose multi-project VPS (translator + webapp + postgres + nginx)

## 📄 Lisensi

© Erlandfatur — proyek pribadi/enterprise.
