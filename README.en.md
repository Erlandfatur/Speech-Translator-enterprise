# 🎙️ Speech Translator — AI Speech-to-Speech Live Translator

> 🌍 **Language:** [🇮🇩 Indonesia](README.md) · [🇬🇧 English](README.en.md)

Bidirectional **real-time voice translation & dubbing** for meetings (English ⇄ Indonesian & multi-language). Speech-in → transcribe → translate → natural voice-out, built for Zoom, Teams & Slack workflows.

> 🌐 **Landing Page:** https://erlandfatur.github.io/Speech-Translator-enterprise/ — interactive, bilingual (EN/ID)

## ✨ Key Features

- **Bidirectional Voice Translation** — 2-way audio pipeline (Audio In → STT → NMT → TTS → Audio Out)
- **Voice Dubbing / Speech-to-Speech** — translations spoken back in natural neural voices
- **Real-time Streaming** — duplex WebSocket, neural VAD, dynamic buffering
- **Speaker Diarization** — labels speakers (Speaker 1, 2, …)
- **Subtitle Overlay** — real-time text fallback during high latency
- **Custom Glossary** — ~370 curated business/technical EN⇄ID terms (98.6% benchmark accuracy)
- **Chrome Extension MV3** — captures mic + tab audio via `tabCapture`

## 🧱 Architecture

```
[Chrome Extension (client)]  --WebSocket-->  [FastAPI Server]
       tabCapture mic+tab                     STT → NMT → TTS
                                              VAD · Diarization · Echo suppression
                                              Virtual Audio (optional, VB-Cable)
```

### Components

| Module | Stack | Path |
|---|---|---|
| **Server** | FastAPI + WebSocket | `server/` |
| **STT** | Groq Whisper Large v3 Turbo + FasterWhisper fallback | `server/pipeline/stt.py` |
| **NMT** | Groq Llama-3.3-70B + Gemini Flash + Google Translate fallback | `server/pipeline/nmt.py` |
| **TTS** | Edge-TTS (Microsoft Neural) + Piper fallback | `server/pipeline/tts.py` |
| **VAD** | Silero VAD v5 (ONNX) | `server/pipeline/vad.py` |
| **Diarization** | SpeakerDiarizer | `server/pipeline/diarization.py` |
| **Virtual Audio** | VB-Audio Virtual Cable (Windows) / BlackHole (macOS) | `server/pipeline/virtual_mic.py` |
| **Extension** | React + TypeScript + Vite (MV3) | `extension/` |

## 🚀 Running the Server

### Prerequisites
- Python 3.11+
- API keys in `server/.env` (see `server/.env.example`)

### Setup
```bash
cd server
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in GROQ_API_KEY & GEMINI_API_KEY
```

### Run
```bash
python main.py
```
Server runs at `http://localhost:8000`, WebSocket at `ws://localhost:8000/ws/translate`.

> **Auth (optional):** set `WS_API_TOKEN` in `.env`, then clients connect with `?token=<value>`. If empty, auth is disabled (dev mode).

## 🖥️ Running the Extension (Dev)

```bash
cd extension
npm install
npm run dev:ext        # build for Chrome extension (watch)
npm run build:ext      # build production extension
```
Load the `extension/dist` folder at `chrome://extensions` (Developer mode → Load unpacked).

## 🧪 Evaluation & Testing

```bash
cd server
python eval_pipeline.py        # NMT accuracy benchmark (requires GROQ/GEMINI key)
python test_full_pipeline.py   # End-to-end pipeline test
```

### Current Benchmark Results (Groq Llama-3.3-70B)
- **Average accuracy:** 98.6%
- **Tests passed (≥90%):** 5/5
- **Average NMT latency:** ~468 ms

## ⚙️ Environment Configuration

Optional variables for latency tuning (`.env.example`):

| Variable | Default | Description |
|---|---|---|
| `BUFFER_MAX_SEC` | `8.0` | Max audio buffer (seconds) |
| `BUFFER_MIN_SEC` | `1.5` | Min audio before flush (seconds) |
| `SILENCE_FLUSH_SEC` | `0.6` | Silence gap for flush |
| `GROQ_COOLDOWN_SEC` | `0.8` | Gap between Groq calls |
| `BUFFER_TAB_FLUSH_SEC` | `2.0` | Tab audio flush window |
| `ALLOWED_ORIGINS` | localhost | CORS allowlist |
| `WS_API_TOKEN` | *(empty)* | WebSocket auth |

## 🚦 CI/CD

- **`.github/workflows/ci.yml`** — lint & build extension (oxlint, tsc, vite) + Python compile smoke test
- **`.github/workflows/pages.yml`** — deploy landing page to GitHub Pages (`docs/` folder)

## ☁️ Deploying the Backend to Render

The repo includes a `render.yaml` (Blueprint). Steps:

1. Go to [render.com](https://render.com) → **New** → **Blueprint** → select this repo.
2. Render reads `render.yaml` → creates the `speech-translator` Web Service from `server/`.
3. **Set secrets** in the service (Settings → Environment):
   `GROQ_API_KEY`, `GEMINI_API_KEY`, `WS_API_TOKEN`.
4. **ALLOWED_ORIGINS** — fill with your landing page/extension origin (e.g. `https://erlandfatur.github.io`).
5. Build & deploy automatically. URL will look like `https://speech-translator.onrender.com`.
   Health check: `https://speech-translator.onrender.com/health` → `{"status":"ok"}`.

> **Note:** `torch`, `sounddevice`, `piper-tts`, `faster-whisper` are heavy; use a plan with enough memory. If you only need STT/NMT/TTS via Groq/Edge APIs, disable heavy local fallbacks.

### Alternative: Fly.io

`server/` also includes a `Dockerfile` & `fly.toml`. Steps:

1. Install & login to the [Fly CLI](https://fly.io/docs/flyctl/): `flyctl auth login`.
2. From `server/`: `flyctl launch` (follow the wizard, reuse the existing `fly.toml`).
3. Set secrets: `flyctl secrets set GROQ_API_KEY=... GEMINI_API_KEY=... WS_API_TOKEN=...`.
4. Deploy: `flyctl deploy`.
5. URL becomes `https://speech-translator.fly.dev` (health: `/health`).

## 🔒 Security

- API keys **only in `.env`** (not committed — in `.gitignore`)
- Strict CORS allowlist (`ALLOWED_ORIGINS`)
- Optional WebSocket auth (`WS_API_TOKEN`)
- Client config is whitelisted (clients cannot inject API keys)
- Echo suppression during TTS playback

## 📄 Additional Documentation

- `ANALISIS_PROYEK.md` — full project analysis & risk assessment
- `SOKUJI_ALIGNMENT_ROADMAP.md` — capability alignment roadmap
- `AGENTS.md` — project & path rules (anti-typo)

## 📄 License

© Erlandfatur — personal/enterprise project.
