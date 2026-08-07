import json
import asyncio
import logging
import base64
import time
import os
import numpy as np
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import auth
import quotas
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


@app.get("/")
async def root():
    return {"name": "Real-Time Speech Translation Server", "status": "ok", "ws_endpoint": "/ws/translate"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# Per-user auth is JWT-based (see auth.py). The server FAILS CLOSED: if
# AUTH_SECRET is unset, no WebSocket is accepted and no tokens are issued.
_ADMIN_KEY = os.getenv("ADMIN_API_KEY", "").strip()


def _require_admin(authorization: str) -> bool:
    """Bearer check for the admin token-issuance endpoints."""
    if not _ADMIN_KEY:
        return False
    scheme, _, cred = authorization.partition(" ")
    return scheme.lower() == "bearer" and cred == _ADMIN_KEY


class TokenRequest(BaseModel):
    user_id: str
    role: str = "user"
    quota: dict = {}
    ttl_seconds: int | None = None


class RevokeRequest(BaseModel):
    token: str


@app.post("/auth/token")
async def issue_token(req: TokenRequest, authorization: str = Header(default="")):
    """Admin-only: issue a per-user JWT. Requires 'Authorization: Bearer <ADMIN_API_KEY>'."""
    if not _require_admin(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        token = auth.create_token(
            req.user_id, role=req.role, quota=req.quota, ttl_seconds=req.ttl_seconds
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"token": token, "expires_in": req.ttl_seconds}


@app.post("/auth/revoke")
async def revoke_token(req: RevokeRequest, authorization: str = Header(default="")):
    """Admin-only: revoke an issued token."""
    if not _require_admin(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not auth.revoke_token(req.token):
        raise HTTPException(status_code=400, detail="Invalid or already-revoked token")
    return {"ok": True}


# Bound the number of concurrently running STT->NMT->TTS pipelines to prevent
# resource exhaustion (memory/CPU) under many simultaneous audio chunks.
_PIPELINE_SEMAPHORE = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_PIPELINES", "4")))

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

# Shared API token removed. Per-user auth is handled by auth.verify_token()
# (JWT). The server rejects all connections when AUTH_SECRET is unset.


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
GROQ_COOLDOWN_SEC = float(os.getenv("GROQ_COOLDOWN_SEC", "1.5"))           # Min gap between calls (was 0.8) – avoids 429
BUFFER_TAB_FLUSH_SEC = float(os.getenv("BUFFER_TAB_FLUSH_SEC", "4.0"))     # Tab audio fixed flush window (was 2.0) – more context for STT

# Whitelist of client-settable config keys. API keys are EXCLUDED so remote
# clients cannot inject their own credentials (multi-tenant abuse) — the server
# always uses its own env keys.
ALLOWED_CONFIG_KEYS = {
    "capture_mode",
    "spoken_lang",
    "target_lang",
    "tts_enabled",
    "virtual_mic_enabled",
    # Per-source language overrides (meeting simulation: mic=ID, tab=EN, dst).
    "mic_spoken_lang",
    "mic_target_lang",
    "tab_spoken_lang",
    "tab_target_lang",
}


class UserSession:
    """Manages a single user connection for bi-directional translation with audio buffering."""
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.user_id: str = "unknown"
        self.token_claims: dict = {}
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

    # Fail closed: require a valid per-user JWT. Reject if auth is not configured.
    if not auth.is_auth_configured():
        logger.error("Auth not configured (AUTH_SECRET missing) — rejecting connection.")
        await websocket.send_text(json.dumps({"type": "error", "message": "Server auth not configured"}))
        await websocket.close(code=4403)
        return

    token = websocket.query_params.get("token", "")
    ok, claims, reason = auth.verify_token(token)
    if not ok:
        logger.warning(f"Unauthorized WebSocket connection rejected: {reason}")
        await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized"}))
        await websocket.close(code=4401)
        return

    user_id = claims.get("sub", "unknown")

    # Enforce per-user connection cap (cost/resource control).
    if not quotas.connection_tracker.try_acquire(user_id):
        logger.warning(f"Connection cap exceeded for user {user_id}")
        await websocket.send_text(json.dumps({"type": "error", "message": "Connection limit reached"}))
        await websocket.close(code=4429)
        return

    session = UserSession(websocket)
    session.user_id = user_id
    session.token_claims = claims
    logger.info(f"New UserSession connected (user={user_id}).")
    
    try:
        while True:
            data_text = await websocket.receive_text()
            if len(data_text.encode("utf-8")) > quotas.max_ws_message_bytes():
                logger.warning(f"Message too large from user {user_id}")
                await websocket.send_text(json.dumps({"type": "error", "message": "Message too large"}))
                await websocket.close(code=4409)
                break
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

                # Per-source language overrides (e.g. meeting: mic=ID->EN, tab=EN->ID).
                if msg_type == "audio_chunk_mic":
                    src_lang = session.config.get("mic_spoken_lang", src_lang)
                    tgt_lang = session.config.get("mic_target_lang", tgt_lang)
                else:
                    src_lang = session.config.get("tab_spoken_lang", src_lang)
                    tgt_lang = session.config.get("tab_target_lang", tgt_lang)

                logger.info(f"Processing {len(pcm_to_process)} bytes audio from [{source_label}]...")

                # Throttle: enforce minimum gap between Groq calls to avoid 429 rate limits
                last_pipeline = session.last_pipeline_time.get(msg_type, 0.0)
                if (now - last_pipeline) < GROQ_COOLDOWN_SEC:
                    logger.info(f"[{source_label}] Cooldown active, skipping this chunk.")
                    continue
                session.last_pipeline_time[msg_type] = now

                # Cost-control: enforce per-user request rate limit.
                if not quotas.rate_limiter.allow(session.user_id):
                    logger.info(f"[{source_label}] Rate limit exceeded for user {session.user_id}.")
                    await session.send_payload({"type": "error", "message": "Rate limit exceeded"})
                    continue

                # Cost-control: enforce per-user monthly usage cap.
                quota_ok, usage = quotas.usage_quota.check(session.user_id)
                if not quota_ok:
                    logger.info(f"[{source_label}] Monthly quota exhausted for user {session.user_id}.")
                    await session.send_payload({"type": "error", "message": "Monthly quota exhausted"})
                    await websocket.close(code=4429)
                    break

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

                        # Record per-user usage for cost control.
                        quotas.usage_quota.add(session.user_id, "stt_sec", stt_lat)
                        quotas.usage_quota.add(session.user_id, "nmt_chars", len(original_text or ""))
                        if tts_lat > 0 and translated_text:
                            quotas.usage_quota.add(session.user_id, "tts_chars", len(translated_text))

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

                async def run_pipeline_guarded(*args):
                    async with _PIPELINE_SEMAPHORE:
                        await run_pipeline(*args)

                asyncio.create_task(run_pipeline_guarded(
                    pcm_to_process, src_lang, tgt_lang, source_label,
                    msg_type, tts_enabled, now
                ))


    except WebSocketDisconnect:
        logger.info("UserSession disconnected.")
        quotas.connection_tracker.release(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        quotas.connection_tracker.release(user_id)

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


