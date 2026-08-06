# Sokuji-Level AI Speech Translator Roadmap & Specification

Documenting the architectural alignment roadmap to elevate **Speech-Translator** to match **Sokuji** (`kizuna-ai-lab/sokuji`) capabilities.

---

## 🎯 Target Architecture & Capability Matrix

| Module | Sokuji Benchmark | Current Baseline | Status |
| :--- | :--- | :--- | :--- |
| **Speech Detection (VAD)** | Silero VAD v5 (ONNX Neural Model) | Silero VAD v5 Neural Engine (`vad.py`) | ✅ **COMPLETED (Phase 1)** |
| **TTS Neural Voices** | Edge-TTS & Bundled ONNX | Microsoft Edge Neural (`edge_tts_engine.py`) | ✅ **COMPLETED (Phase 2)** |
| **Stream Latency** | WebSockets Duplex Buffer | Sub-300ms Dynamic VAD Speech Flush | ✅ **COMPLETED (Phase 3)** |
| **Speaker Diarization** | Multi-speaker identification | Real-time SpeakerDiarizer (`diarization.py`) | ✅ **COMPLETED (Phase 4)** |
| **Translation Engine** | Llama 3 / Qwen / Gemini | Groq Llama-3.3 70B (Score >91.4%) | ✅ **Maintained** |
| **Virtual Audio Route** | Virtual Cable / BlackHole | VB-Audio Virtual Cable (`virtual_mic.py`) | ✅ **Maintained** |
| **Subtitles UI** | Floating Subtitle Overlay | Glassmorphism Overlay (`content.js`) | ✅ **Maintained** |

---

## 🚀 Execution Phases Summary

### Phase 1: Silero VAD v5 Integration (Neural Speech Detection) ✅
- Created `server/pipeline/vad.py` using Silero VAD v5 ONNX model.
- Filters out keyboard typing, background fan noise, and non-speech sounds.

### Phase 2: Edge-TTS Neural Voice Integration ✅
- Created `server/pipeline/edge_tts_engine.py` streaming ultra-realistic Microsoft Neural TTS voices (`id-ID-ArdiNeural` & `en-US-ChristopherNeural`).

### Phase 3: Dynamic Audio Sliding Window & Instant Response ✅
- Optimized buffer flush with sub-300ms dynamic VAD speech boundary flush.

### Phase 4: Multi-Speaker Diarization ✅
- Created `server/pipeline/diarization.py` to identify and tag distinct speakers (`Pembicara 1`, `Pembicara 2`, etc.).

