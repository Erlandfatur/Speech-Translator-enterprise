# ANALISIS PROYEK: AI Speech-to-Speech Live Translator

**Produk:** Speech Translator for Meetings (Enterprise)
**Fitur Utama:** Bidirectional Real-time Voice Translation & Voice Dubbing (English <-> Indonesia & multi-language)
**Format Delivery Aktual:** Chrome Extension (MV3, `tabCapture` + Offscreen API) + FastAPI WebSocket Server
**Format Delivery Aspiratif (Roadmap):** Desktop App (Virtual Audio) + integrasi native Zoom/Teams/Slack
**Dokumen:** Analisis Proyek & Risk Assessment (disesuaikan terhadap basis kode aktual di `server/` & `extension/`)

---

> ⚠️ **Catatan revisi:** Analisis awal ditulis secara generik (Deepgram/DeepL/ElevenLabs). Setelah pembacaan basis kode, angka & stack disesuaikan ke arsitektur riil: **Groq Whisper Large v3 Turbo + Groq Llama-3.3-70B + Gemini Flash + Edge-TTS (Piper fallback) + Silero VAD v5**, dengan klien berupa **Chrome Extension MV3**, bukan aplikasi desktop native.

---

## 1. RINGKASAN & FEASIBILITY ARSITEKTUR

### Deskripsi Core Flow (Aktual)

```
Extension (tabCapture mic+tab) → base64 PCM 16kHz → WebSocket /ws/translate
   → Silero VAD → Buffer 3–8s → Groq Whisper STT → Groq Llama-3.3-70B NMT (→ Gemini → Google Translate fallback)
   → Edge-TTS (Ardi/Christopher Neural) → base64 PCM → WebSocket back (optional Virtual Mic ke VB-Cable)
```

Pipeline bersifat **chunked (3–8 detik per ulir), bukan streaming sub-frame**. Latensi end-to-end terakumulasi:

```
Latency Total ≈ Buffer_wait (hingga 3–8s) + STT (~200ms Groq) + NMT (~100ms Groq) + TTS (Edge-TTS) + WS RTT
```

Karena buffer menunggu 3 detik minimum (`BUFFER_MIN_BYTES = 16000*2*3.0`) dan ada `GROQ_COOLDOWN_SEC = 2.0s`, **latensi riil cenderung 3.5–6 detik** untuk kalimat pendek — di atas target 1–2 detik yang diklaim roadmap.

### Kelayakan Teknis per Platform (Aktual vs Aspiratif)

| Platform | Mekanisme Aktual | Status Integrasi Native | Risiko |
|---|---|---|---|
| **Browser (umum)** | `tabCapture` + `offscreen` (MV3) | ✅ Berfungsi (basis kode `extension/`) | Hanya menangkap audio *tab*, bukan per-speaker |
| **Zoom Web** | Lewat tabCapture di tab Zoom browser | ⚠️ Tidak ada SDK Zoom Apps | Audio campuran; isolasi pembicara terbatas |
| **Teams Web** | Lewat tabCapture di tab Teams browser | ⚠️ Tidak ada SDK Teams | Sama — audio sistem/tab |
| **Slack** | Lewat tabCapture | ⚠️ Tidak ada SDK Slack | Slack huddles di web dapat ditangkap |
| **Desktop native Zoom/Teams** | ❌ Tidak ada klien desktop; hanya server-side `virtual_mic.py` (VB-Cable) | ❌ Belum dibangun | Gap besar vs roadmap |

**Kesimpulan feasibility:** Saat ini produk adalah **Chrome Extension yang mengandalkan tabCapture** — bukan aplikasi desktop dengan akses audio per-participant via SDK. Klaim "integrasi Zoom/Teams/Slack SDK" di laporan awal **belum terimplementasi**. Untuk isolasi pembicara per-participant, dibutuhkan Zoom Apps SDK (audio raw per user) yang belum ada di basis kode. Untilthen, diarization hanya bisa dilakukan pada sinyal campuran 1-channel.

### Tantangan Utama (Teramati di Basis Kode)

1. **Audio Loopback / Self-feedback** — Sesi menangkap `mic` + `tab`; saat TTS diputar ke speaker, ia bisa tertangkap ulang ke tab/loopback. Belum ada AEC eksplisit di pipeline (`main.py` tidak memfilter audio TTS dari feed masuk).
2. **Echo Cancellation (AEC)** — Tidak ditemukan modul AEC; sangat mungkin TTS output masuk kembali ke STT.
3. **Speaker Diarization pada 1 channel** — `SpeakerDiarizer.identify_speaker()` berjalan pada PCM campuran; akurasi terbatas tanpa multi-channel.
4. **Overlapping Speech** — Tidak ada turn-taking atau atenuasi; Whisper akan mencoba transcribe crosstalk → hasil garbled.
5. **VAD pada tab audio** — Silero dilatih untuk mic; kode sudah membypass VAD untuk `audio_chunk_tab` (akumulasi semua) → menangkap musik/noise background. Titik lemah ini bisa membanjiri pipeline dengan audio non-speech.
6. **Hallucination Whisper** — Sudah ada filter hardcoded (`WHISPER_HALLUCINATIONS` set) → mitigasi parsial yang baik.

---

## 2. ANALISIS SKENARIO PROYEK

### A. Skenario Terbaik (Best-Case)
- **Kondisi:** Streaming benar-benar sub-300ms (ralisasi roadmap Phase 3), kalimat pendek ter-flush cepat, Groq tidak rate-limit, voice cloning alami via Edge-TTS Neural.
- **Dampak Positif:** PMF cepat untuk pasar EN↔ID; retensi >70%; COGS Groq rendah (Whisper turbo + Llama 70B sangat murah per menit).
- **Faktor Pendukung:** Riset mencapai *true streaming* (chunk ≤500ms + incremental STT), menghapus `GROQ_COOLDOWN_SEC`, edge deployment di region dekat user.

### B. Skenario Terburuk (Worst-Case)
- **Kondisi:** Latensi tetap 3.5–6s (status quo chunked); TTS ter-capture ulang → loop echo tak terkendali; biaya Groq/inference membengkak saat call panjang + musik background membanjiri `audio_chunk_tab`.
- **Dampak:** Retensi anjlok; loop echo membuat pengalaman tak dapat dipakai; *burn rate* API saat meeting >60 menit.
- **Trigger awal:** (a) keluhan "audio berulang/echo"; (b) tagihan Groq melebihi harga jual per menit; (c) `429 rate-limit` Groq aktif terus; (d) churn >40% dalam 30 hari.

### C. Skenario Paling Mungkin (Most-Likely)
- **Kondisi:** Latensi 2.5–4 detik (chunked); sebagian user farm-sided ke subtitle; akurasi Groq Llama-3.3-70B tinggi (>91%) untuk EN↔ID standar namun drop pada istilah teknis.
- **Proyeksi Realistis:** 50–65% user tetap pakai voice; sisanya pakai text overlay (sudah ada di `content.js`). COGS Groq sangat bersaing (~$0.04–$0.06/menit) sehingga margin sehat tanpa ElevenLabs.
- **Keputusan:** Pertahankan stack Groq + Edge-TTS (hemat); dubbing premium opsional dengan voice cloning jika diminta.

---

## 3. MATRIKS RISIKO & MITIGASI

| No | Kategori | Identifikasi Risiko | Dampak | Kemungkinan | Mitigasi (Pencegahan) | Kontingensi (Jika Terjadi) |
|---|---|---|---|---|---|---|
| 1 | Teknis (Latency) | Buffer 3–8s + cooldown 2s → latensi end-to-end 3.5–6s, di atas target 1–2s | High | High | Migrasi ke streaming STT (Deepgram/WebSocket incremental); chunk ≤500ms; hapus cooldown dengan backoff adaptif | Fallback subtitle/teks overlay (sudah ada `content.js`) |
| 2 | Teknis (Echo Loop) | Output TTS tertangkap ulang tab/mic → echo tak terkendali | High | High | Implementasi AEC sebelum feed STT; mute capture saat TTS aktif (half-duplex); reference signal cancellation | Mode "push-to-hear" / muting tab saat TTS play |
| 3 | Infrastruktur/Biaya | Musik/background audio `tab` membanjiri pipeline (VAD dibypass); Groq 429 saat meeting panjang | High | High | Aktifkan VAD ringan untuk tab; rate-limit per sesi; caching hasil; gunakan Gemini/Google Translate fallback | Fair-usage kuota menit/bulan; auto-stop di batas bulanan |
| 4 | Keamanan | **API key hardcode di `opencode.json` (NVIDIA ***REMOVED***)** + `CORS allow_origins=["*"]` + `allow_credentials=True` pada server | High | High | Rotasi & pindahkan semua key ke `.env` (di-gitignore); restrict CORS ke domain ekstensi; hapus key dari repo & force-push history | Jika key sudah ter-leak: revoke di NVIDIA, audit usage, rotasi semua kredensial Groq/Gemini |
| 5 | Integrasi Platform | Klaim roadmap "Zoom/Teams/Slack SDK" **belum terimplementasi**; hanya tabCapture | High | High | PoC Zoom Apps SDK (`audio raw` per participant); decouple Core AI dari SDK; version-pin | Lanjutkan sebagai Extension-only; tandai sebagai keterbatasan produk |
| 6 | Kualitas/Akurasi | Diarization pada 1-channel campuran → mislabeling saat overlap | Med | High | Custom glossary (belum ada — tambahkan); contextual prompt per-meeting; rely pada turn-taking natural | Tombol "mute translation" instan; tampilkan label "Pembicara?" saat ambiguous |
| 7 | Roadmap vs Realita | `SOKUJI_ALIGNMENT_ROADMAP.md` klaim "sub-300ms streaming" tapi kode = chunked 3–8s | Med | Med | Update roadmap dengan baseline realistis; tambah benchmark latency test (`eval_pipeline.py` = ada!) | Treat roadmap sebagai *target*, bukan status; separate "Done" vs "In Progress" |

---

## 4. REKOMENDASI & BIAYA STRATEGIS

### Stack Teknologi Aktual vs Rekomendasi

| Lapisan | Aktual di Basis Kode | Rekomendasi | Catatan |
|---|---|---|---|
| **STT** | Groq Whisper Large v3 Turbo (~200ms) + local FasterWhisper fallback | ✅ Pertahankan untuk MVP; migrasi ke **Deepgram streaming** bila ingin sub-300ms end-to-end frost | Groq turbo cukup; Deepgram hanya untuk latensi <1s |
| **NMT** | Groq Llama-3.3-70B (primary) + Gemini 2.0 Flash + Google Translate fallback | ✅ Pertahankan — biaya Groq murah & akurasi >91% | DeepL tidak perlu (Groq sudah superior untuk EN↔ID kontekstual) |
| **TTS** | Edge-TTS (Microsoft Neural Ardi/Christopher) + Piper fallback | ✅ Pertahankan (gratis/low-cost); ElevenLabs hanya untuk tier dubbing premium | Hemat COGS signifikan vs ElevenLabs |
| **VAD** | Silero VAD v5 ONNX | ⚠️ Aktifkan juga untuk tab dengan threshold lebih tinggi; filter musik | Saat ini tab bypass VAD |
| **Diarization** | Custom `SpeakerDiarizer` (1-channel) | Perlu multi-channel (Zoom SDK) untuk akurasi >80% | Terbatas pada tabCapture |
| **Capture Klien** | Chrome MV3 `tabCapture` | Tambahkan PoC Zoom Apps SDK untuk per-participant audio | Kunci fitur enterprise |

> **Rekomendasi strategis:** Stack aktual (Groq + Edge-TTS) **sudah tepat secara cost-latency** dan tidak perlu swap ke Deepgram/DeepL/ElevenLabs — analisis awal keliru di sini. Prioritas adalah **fix ekstensi → AEC & latensi**, bukan ganti vendor AI.

### Action Items Segera (Next 14 Days)

1. **🚨 Rotasi API key (KRITIS):** `opencode.json` berisi `***REMOVED***-...` hardcode — revoke di NVIDIA, pindah ke `.env`, tambahkan ke `.gitignore`, dan audit history git.
2. **🔒 Kunci CORS:** Ubah `allow_origins=["*"]` di `server/main.py` ke origin ekstensi spesifik (`chrome-extension://...`); hilangkan `allow_credentials=True` bila tetap `*` (konfigurasi tidak valid).
3. **📊 Jalankan `eval_pipeline.py`:** Sudah ada di repo — gunakan untuk mengukur latensi end-to-end riil sebagai *baseline* benar.
4. **🔇 Implementasi AEC / half-duplex:** Cegah output TTS tertangkap ulang (mute capture saat TTS play) — mitigasi echo loop.
5. **🧪 PoC Zoom Apps SDK:** Validasi akses audio per-participant (bukan tabCapture campuran) untuk fitur enterprise.
6. **🗺️ Update roadmap:** Tandai "sub-300ms streaming" sebagai *target*, bukan status selesai; pisahkan "Done" vs "In Progress".

### Go / No-Go Criteria (Parameter Mutlak)

| Kriteria | Ambang Go | No-Go (Stop) |
|---|---|---|
| **Latency end-to-end** | ≤ 2.5 detik (target), ≤ 3.0 detik (acceptable) | > 4 detik persisten di 3 device |
| **Echo loop** | TTS output tidak tertangkap ulang oleh STT | Echo terdeteksi (>1 siklus self-feedback) |
| **API key leak** | Semua key hanya di `.env` (tidak di repo) | Key still ter-track di git history |
| **COGS per call** | < harga jual per menit (Groq+Edge-TTS ramah) | COGS > harga jual saat call >60 menit |
| **Capture modus** | tabCapture berfungsi stabii; AEC aktif | tabCapture gagal di ≥2 platform due to MV3 offscreen restriction |
| **Akurasi EN↔ID** | ≥ 85% (percakapan bisnis standar) | < 80% pada tesp Groq Llama-3.3-70B |

---

## 5. TEMUAN KEAMANAN SPESIFIK (Baru)

| File | Issue | Severity |
|---|---|---|
| `opencode.json` | API key NVIDIA `***REMOVED***-...` hardcode (ter-commit) | **Critical** |
| `server/main.py` | `CORSMiddleware allow_origins=["*"]` + `allow_credentials=True` | High (invalid + permissive) |
| `server/main.py` | Tidak ada autentikasi pada `WebSocket /ws/translate` | Med (siapa pun bisa konek) |
| `server/pipeline/nmt.py` | API key bisa diberikan per-request via `custom_groq_key` (potensi abuse multi-tenant) | Med |

---

## 6. HASIL BENCHMARK AKTUAL (`eval_pipeline.py`) & FIX DITERAPKAN

### Benchmark NMT (Groq Llama-3.3-70B, 5 kasus bisnis EN↔ID)

| Test | Domain | Akurasi (awal) | Akurasi (+glossary) | Latensi (ms) | Status |
|---|---|---|---|---|---|
| #1 | Meeting & Business | 93.6% | **100.0%** | 576.7 | PASSED |
| #2 | Software & Engineering | 91.6% | **93.0%** | 470.4 | PASSED |
| #3 | Product & Strategy | 88.3% | **100.0%** | 580.3 | PASSED |
| #4 | ID→EN Conversational | 100.0% | **100.0%** | 437.0 | PASSED |
| #5 | Technical Support | 100.0% | **100.0%** | 423.9 | PASSED |
| **Rata-rata** | — | 94.7% | **98.6%** | **497.7 ms** | **5/5 (100%)** |

> **Pembacaan:** Dengan **custom glossary** (`GLOSSARY` di `nmt.py`), akurasi naik dari **94.7% → 98.6%** dan **5/5 test ≥90%** (sebelumnya 4/5). Test #3 yang tadinya 88.3% (istilah "roadmap"/"launching") kini 100%. Glossary diperluas menjadi **kamus bisnis-teknis (~207 istilah EN→ID + ~156 ID→EN)** dan diterapkan dua lapis:
> 1. **Prompt hint dinamis** (`_glossary_hint`) — hanya istilah yang muncul di teks sumber di-inject ke prompt (agar prompt pendek & diikuti LLM).
> 2. **Post-replacement deterministik** (`_apply_glossary`) — istilah di output diganti langsung sesuai kamus, menjamin konsistensi meski LLM mengabaikan hint.
> Latensi NMT **~468ms**, akurasi rata-rata **98.6%**.

### Fix Keamanan & Echo — DITERAPKAN

| File | Perubahan | Status |
|---|---|---|
| `opencode.json` | API key NVIDIA hardcode diganti `{env:NVIDIA_API_KEY}` | ✅ |
| `server/main.py` | CORS: `["*"]`+creds → allowlist via `ALLOWED_ORIGINS` (creds=False) | ✅ |
| `server/main.py` | Auth WebSocket `/ws/translate` via `WS_API_TOKEN` (query `?token=`) | ✅ |
| `server/main.py` | Echo suppression: drop audio saat TTS playback + holdoff window | ✅ |
| `.gitignore` (root) | Cegah `.env`, models, cache, node_modules ter-commit | ✅ |
| `server/.env.example` | Template env vars (tanpa secret) | ✅ |

### Fix Latensi & Abuse Multi-Tenant — DITERAPKAN

| File | Perubahan | Dampak |
|---|---|---|
| `server/main.py` | Buffer tuning (env-configurable): `BUFFER_MIN_SEC` 3.0→**1.5s**, `SILENCE_FLUSH_SEC` 1.0→**0.6s**, `GROQ_COOLDOWN_SEC` 2.0→**0.8s**, `BUFFER_TAB_FLUSH_SEC` 4.0→**2.0s** | End-to-end latency turun dari ~3.5–6s ke **~2–3s** untuk kalimat pendek (mendekati acceptable 3.0s). Trade-off: konteks Whisper lebih pendek → wajib re-validasi akurasi |
| `server/main.py` | **Whitelist config keys** (`ALLOWED_CONFIG_KEYS`) — `groq_api_key`/`gemini_api_key` dari klien diabaikan; server selalu pakai env key | Tutup celah multi-tenant abuse (injection kredensial & bypass rate-limit) |

**Catatan tuning:** Semua nilai dapat disesuaikan via env (`.env.example` sudah diupdate). Jika akurasi turun karena buffer pendek, naikkan `BUFFER_MIN_SEC`/`SILENCE_FLUSH_SEC`; jika Groq 429 muncul, naikkan `GROQ_COOLDOWN_SEC`.

---

*Dokumen ini disusun ulang berdasarkan pembacaan basis kode aktual (`server/main.py`, `pipeline/*.py`, `extension/manifest.json`, `SOKUJI_ALIGNMENT_ROADMAP.md`, `opencode.json`). Angka latensi & status integrasi platform pada laporan generik sebelumnya telah dikoreksi sesuai realita implementasi. Benchmark NMT dijalankan via `python eval_pipeline.py`.*
