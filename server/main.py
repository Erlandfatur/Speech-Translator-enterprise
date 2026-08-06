import json
import asyncio
import logging
import base64
import time
import numpy as np
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline.stt import FasterWhisperSTT
from pipeline.nmt import GeminiTranslator
from pipeline.tts import StreamingTTS
from pipeline.virtual_mic import VirtualMicManager
from pipeline.vad import SileroVAD
from pipeline.diarization import SpeakerDiarizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SpeechTranslatorServer")

app = FastAPI(
    title="Real-Time Speech Translation Server",
    description="WebSocket Gateway for 1-on-1 Meeting Speech-to-Speech & Speech-to-Text Translation"
)


@app.get("/health")
async def health():
    return {"status": "ok"}

# Allowlist: Chrome extension IDs (set via env) + localhost dev origins.
# NOTE: MV3 extensions have origin "chrome-extension://<EXTENSION_ID>".
import os
_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://localhost:8000"
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Shared API token. Set WS_API_TOKEN in .env. If empty, auth is disabled (dev only).
_WS_TOKEN = os.getenv("WS_API_TOKEN", "").strip()


def _authorized(websocket: WebSocket) -> bool:
    """Validate client via ?token= query param. Disabled when WS_API_TOKEN is empty."""
    if not _WS_TOKEN:
        return True
    token = websocket.query_params.get("token", "")
    return token == _WS_TOKEN


# Global AI Engine Instances
stt_engine = FasterWhisperSTT()
nmt_engine = GeminiTranslator()
tts_engine = StreamingTTS()
virtual_mic_engine = VirtualMicManager()
vad_engine = SileroVAD()



# Audio Buffering Constants (16kHz 16-bit mono = 32,000 bytes/sec)
# Configurable via env to tune latency vs. context. Lower = faster flush, less context.
BUFFER_MAX_BYTES  = float(os.getenv("BUFFER_MAX_SEC", "8.0")) * 16000 * 2  # Max seconds – full-sentence context
BUFFER_MIN_BYTES  = float(os.getenv("BUFFER_MIN_SEC", "1.5")) * 16000 * 2  # Min seconds before flush (was 3.0)
SILENCE_FLUSH_SEC = float(os.getenv("SILENCE_FLUSH_SEC", "0.6"))           # Flush after short speech pause (was 1.0)
GROQ_COOLDOWN_SEC = float(os.getenv("GROQ_COOLDOWN_SEC", "0.8"))           # Min gap between calls (was 2.0)
BUFFER_TAB_FLUSH_SEC = float(os.getenv("BUFFER_TAB_FLUSH_SEC", "2.0"))     # Tab audio fixed flush window (was 4.0)

# Whitelist of client-settable config keys. API keys are EXCLUDED so remote
# clients cannot inject their own credentials (multi-tenant abuse) — the server
# always uses its own env keys.
ALLOWED_CONFIG_KEYS = {
    "capture_mode",
    "spoken_lang",
    "target_lang",
    "tts_enabled",
    "virtual_mic_enabled",
}


class UserSession:
    """Manages a single user connection for bi-directional translation with audio buffering."""
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.config: dict = {
            "capture_mode": "both",
            "spoken_lang": "en",
            "target_lang": "id",
            "tts_enabled": True,
            "virtual_mic_enabled": False
        }
        self.buffers: Dict[str, bytearray] = {
            "audio_chunk_mic": bytearray(),
            "audio_chunk_tab": bytearray()
        }
        self.last_speech_time: Dict[str, float] = {
            "audio_chunk_mic": time.time(),
            "audio_chunk_tab": time.time()
        }
        self.last_text: Dict[str, str] = {
            "audio_chunk_mic": "",
            "audio_chunk_tab": ""
        }
        self.last_text_time: Dict[str, float] = {
            "audio_chunk_mic": 0.0,
            "audio_chunk_tab": 0.0
        }
        self.last_pipeline_time: Dict[str, float] = {
            "audio_chunk_mic": 0.0,
            "audio_chunk_tab": 0.0
        }
        self.diarizer = SpeakerDiarizer()
        # Echo mitigation: flag set while TTS audio is being delivered, plus a
        # holdoff window so the TTS playback echo is not re-captured and fed to STT.
        self.tts_active: Dict[str, bool] = {
            "audio_chunk_mic": False,
            "audio_chunk_tab": False
        }
        self.tts_active_until: Dict[str, float] = {
            "audio_chunk_mic": 0.0,
            "audio_chunk_tab": 0.0
        }

    async def _release_tts_lock(self, channel: str, delay: float):
        """Release the echo-suppression lock after the TTS playback window elapses."""
        await asyncio.sleep(delay)
        self.tts_active[channel] = False
        self.tts_active_until[channel] = 0.0


    async def send_payload(self, payload: dict):
        try:
            if self.websocket.client_state.name != 'CONNECTED':
                return
            await self.websocket.send_text(json.dumps(payload))
        except Exception as e:
            logger.error(f"Error sending payload: {e}")

@app.websocket("/ws/translate")
async def websocket_translate_endpoint(websocket: WebSocket):
    await websocket.accept()
    if not _authorized(websocket):
        logger.warning("Unauthorized WebSocket connection rejected.")
        await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized"}))
        await websocket.close(code=4401)
        return
    session = UserSession(websocket)
    logger.info("New UserSession connected.")
    
    try:
        while True:
            data_text = await websocket.receive_text()
            message = json.loads(data_text)
            msg_type = message.get("type")

            if msg_type == "ping":
                continue

            if msg_type == "config":
                incoming = message.get("config", {})
                # Only apply whitelisted keys; silently drop anything else
                # (e.g. client-supplied groq_api_key / gemini_api_key).
                filtered = {k: v for k, v in incoming.items() if k in ALLOWED_CONFIG_KEYS}
                session.config.update(filtered)
                logger.info(f"Updated user config (filtered): {session.config}")
                
            elif msg_type in ["audio_chunk_mic", "audio_chunk_tab"]:
                b64_audio = message.get("audio_b64", "")
                if not b64_audio:
                    continue

                pcm_bytes = base64.b64decode(b64_audio)
                logger.info(f"Received audio chunk [{msg_type}] of {len(pcm_bytes)} bytes")
                pcm_data = np.frombuffer(pcm_bytes, dtype=np.int16)
                if len(pcm_data) == 0:
                    continue

                # Calculate audio energy (RMS)
                pcm_float = pcm_data.astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(pcm_float**2)))

                # Neural Voice Activity Detection (Silero VAD v5)
                is_speech = vad_engine.is_speech(pcm_bytes, 16000)

                now = time.time()
                buf = session.buffers[msg_type]

                # Echo mitigation: while TTS output for this channel is still playing
                # (within the holdoff window), drop incoming audio so the speaker
                # echo is NOT re-captured and fed back into the STT pipeline.
                if now < session.tts_active_until[msg_type] or session.tts_active[msg_type]:
                    logger.info(f"[{msg_type}] Suppressing echo during TTS playback.")
                    continue

                # VAD: Silero was trained on microphone speech, not browser-resampled tab audio.
                # For TAB: bypass VAD and RMS, just accumulate everything to guarantee we capture audio.
                # For MIC: use proper Silero VAD.
                if msg_type == "audio_chunk_tab":
                    should_accumulate = True
                else:
                    should_accumulate = is_speech or (rms >= 0.0008)

                if should_accumulate:
                    buf.extend(pcm_bytes)
                    session.last_speech_time[msg_type] = now

                # Determine if we should process buffer (Dynamic VAD boundary flush)
                should_process = False
                buf_len = len(buf)
                time_since_speech = now - session.last_speech_time[msg_type]

                if buf_len >= BUFFER_MAX_BYTES:
                    # Buffer full (8s) – always flush
                    should_process = True
                elif msg_type == "audio_chunk_tab" and buf_len >= (16000 * 2 * BUFFER_TAB_FLUSH_SEC):
                    # For tab audio, since we disabled VAD, chunk exactly every TAB_FLUSH window
                    should_process = True
                elif buf_len >= BUFFER_MIN_BYTES and time_since_speech >= SILENCE_FLUSH_SEC:
                    # Enough audio (3s+) and there's a natural speech pause – flush
                    should_process = True
                # Don't flush tiny buffers (< 3s) – they produce short, context-free clips




                if not should_process:
                    continue

                # Extract buffered audio for processing and clear session buffer
                pcm_to_process = bytes(buf)
                buf.clear()

                src_lang = session.config.get("spoken_lang", "en")
                tgt_lang = session.config.get("target_lang", "id")
                source_label = "MIC (Self)" if msg_type == "audio_chunk_mic" else "TAB (Media)"
                tts_enabled = session.config.get("tts_enabled", True)

                logger.info(f"Processing {len(pcm_to_process)} bytes audio from [{source_label}]...")

                # Throttle: enforce minimum gap between Groq calls to avoid 429 rate limits
                last_pipeline = session.last_pipeline_time.get(msg_type, 0.0)
                if (now - last_pipeline) < GROQ_COOLDOWN_SEC:
                    logger.info(f"[{source_label}] Cooldown active, skipping this chunk.")
                    continue
                session.last_pipeline_time[msg_type] = now

                # Run the full STT→NMT→TTS pipeline as a background task
                # so the WebSocket receive loop is never blocked (prevents disconnect on Groq retries)

                async def run_pipeline(pcm, src, tgt, sl, mt, te, now_ts):
                    try:
                        original_text, stt_lat = await asyncio.to_thread(
                            stt_engine.transcribe_chunk, pcm, 16000, src
                        )
                        clean_text = original_text.strip()
                        if not clean_text or clean_text in [".", "..", "..."]:
                            return

                        # Filter known Whisper hallucination phrases (produced on silence/background music)
                        WHISPER_HALLUCINATIONS = {
                            "thank you.", "thank you", "thanks.", "thanks",
                            "okay.", "okay", "ok.", "ok",
                            "bye.", "bye", "bye-bye.", "bye-bye",
                            "you.", "no.", "yes.", "yeah.",
                            "oh.", "oh yeah.", "oh yeah",
                            "i'm going to go to the next one.",
                            "you can have a lot of water.",
                            "subtitles by the amara.org community",
                            "www.moviewavs.com",
                            # Indonesian hallucinations from Whisper
                            "terima kasih.", "terima kasih",
                            "terima kasih telah menonton!", "terima kasih telah menonton.", "terima kasih telah menonton",
                            "ya.", "ya", "oke.", "oke", "baiklah.", "baiklah"
                        }
                        if clean_text.lower() in WHISPER_HALLUCINATIONS:
                            logger.info(f"[{sl}] Hallucination filtered: '{clean_text}'")
                            return

                        last_text = session.last_text.get(mt, "")
                        last_time = session.last_text_time.get(mt, 0)
                        if clean_text.lower() == last_text.lower() and (now_ts - last_time) < 4.0:
                            logger.info(f"[{sl}] Filtered duplicate: '{clean_text}'")
                            return
                        session.last_text[mt] = clean_text
                        session.last_text_time[mt] = now_ts

                        logger.info(f"[{sl} STT ({stt_lat*1000:.1f}ms)]: {clean_text}")


                        translated_text, nmt_lat = await asyncio.to_thread(
                            nmt_engine.translate, original_text, src, tgt
                        )
                        logger.info(f"[{sl} NMT ({nmt_lat*1000:.1f}ms)]: {translated_text}")

                        audio_b64_out = ""
                        tts_lat = 0.0
                        virtual_mic_enabled = session.config.get("virtual_mic_enabled", False)
                        if te and translated_text.strip():
                            tts_pcm, tts_lat = await asyncio.to_thread(
                                tts_engine.synthesize, translated_text, tgt
                            )
                            if tts_pcm:
                                audio_b64_out = base64.b64encode(tts_pcm).decode('utf-8')
                                if virtual_mic_enabled:
                                    asyncio.create_task(asyncio.to_thread(
                                        virtual_mic_engine.play_tts_to_virtual_mic, tts_pcm
                                    ))

                        total_latency = (stt_lat + nmt_lat + tts_lat) * 1000.0
                        speaker_tag = session.diarizer.identify_speaker(pcm, sl)
                        logger.info(f"Total Pipeline Latency: {total_latency:.1f} ms [{speaker_tag}]")

                        # Echo mitigation: estimate TTS playback duration (16kHz mono
                        # int16 = 32,000 bytes/sec) + a short settle buffer, and suppress
                        # incoming audio for that channel during playback.
                        if audio_b64_out:
                            audio_bytes_len = len(base64.b64decode(audio_b64_out))
                            playback_sec = audio_bytes_len / 32000.0
                            holdoff = min(playback_sec + 0.3, 8.0)
                            session.tts_active[mt] = True
                            session.tts_active_until[mt] = time.time() + holdoff
                            logger.info(f"[{mt}] TTS playback ~{playback_sec:.2f}s, echo holdoff {holdoff:.2f}s")
                            asyncio.create_task(session._release_tts_lock(mt, holdoff))

                        await session.send_payload({
                            "type": "translation_result",
                            "source": "mic" if mt == "audio_chunk_mic" else "tab",
                            "speaker": speaker_tag,
                            "original_text": original_text,
                            "translated_text": translated_text,
                            "src_lang": src,
                            "tgt_lang": tgt,
                            "audio_b64": audio_b64_out,
                            "latency_ms": round(total_latency, 1)
                        })
                    except Exception as pipe_err:
                        logger.error(f"Pipeline error: {pipe_err}")

                asyncio.create_task(run_pipeline(
                    pcm_to_process, src_lang, tgt_lang, source_label,
                    msg_type, tts_enabled, now
                ))


    except WebSocketDisconnect:
        logger.info("UserSession disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


