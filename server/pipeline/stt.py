import os
import io
import time
import wave
import logging
import numpy as np
from typing import Tuple, Optional
from dotenv import load_dotenv

logger = logging.getLogger("STTEngine")
logger.setLevel(logging.INFO)

load_dotenv()

def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Convert raw 16kHz 16-bit mono PCM bytes to in-memory WAV file bytes."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return wav_io.getvalue()


class FasterWhisperSTT:
    """
    Hybrid Speech-to-Text Engine:
    - Primary: Groq Whisper API (whisper-large-v3-turbo) for ultra-fast (~200ms) & highly accurate transcription.
    - Fallback: Local FasterWhisper CPU model if Groq API key is missing or offline.
    """
    def __init__(self, model_size: str = "tiny"):
        self.model_size = model_size
        self.groq_client = None
        self.local_model = None
        self._init_groq()

    def _init_groq(self):
        load_dotenv(override=True)
        api_key = os.getenv("GROQ_API_KEY")
        if api_key and api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=api_key)
                logger.info("Groq Whisper STT initialized successfully (Primary engine).")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}. Falling back to local FasterWhisper.")
                self.groq_client = None
        else:
            logger.info("GROQ_API_KEY not set. Using local FasterWhisper engine.")

    def _ensure_local_model(self):
        if self.local_model is None:
            from faster_whisper import WhisperModel
            logger.info(f"Loading local FasterWhisper model '{self.model_size}' on CPU...")
            self.local_model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            logger.info("Local FasterWhisper loaded successfully.")

    def _transcribe_groq(self, pcm_bytes: bytes, lang_code: str, custom_groq_key: Optional[str] = None) -> Optional[str]:
        api_key = custom_groq_key or os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            return None
        try:
            from groq import Groq
            client = Groq(api_key=api_key) if custom_groq_key else (self.groq_client or Groq(api_key=api_key))
            wav_bytes = pcm_to_wav_bytes(pcm_bytes)
            audio_file = ("speech.wav", wav_bytes, "audio/wav")
            
            kwargs = {
                "file": audio_file,
                "model": "whisper-large-v3-turbo",
                "response_format": "text",
                "temperature": 0.0
            }
            if lang_code:
                kwargs["language"] = lang_code

            transcription = client.audio.transcriptions.create(**kwargs)
            text = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
            return text

        except Exception as e:
            logger.warning(f"Groq STT transcription error: {e}. Falling back to local model.")
            return None

    def _transcribe_local(self, pcm_bytes: bytes, lang_code: str) -> str:
        self._ensure_local_model()
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, info = self.local_model.transcribe(
            audio_data,
            beam_size=1,
            language=lang_code,
            vad_filter=True,
            condition_on_previous_text=False
        )
        return " ".join([segment.text for segment in segments]).strip()

    def transcribe_chunk(self, pcm_bytes: bytes, sample_rate: int = 16000, language: Optional[str] = None, custom_groq_key: Optional[str] = None) -> Tuple[str, float]:
        """
        Transcribe raw audio bytes (Int16) to text using Groq Whisper with local fallback.
        """
        start_time = time.time()
        if not pcm_bytes or len(pcm_bytes) == 0:
            return "", 0.0

        if not language or language == "auto":
            lang_code = None
        elif language.startswith("en"):
            lang_code = "en"
        elif language.startswith("id"):
            lang_code = "id"
        else:
            lang_code = language[:2]

        # Try Groq API first
        text = self._transcribe_groq(pcm_bytes, lang_code, custom_groq_key=custom_groq_key)
        if text is not None:
            latency = time.time() - start_time
            logger.info(f"Groq STT Completed in {latency*1000:.1f}ms")
            return text, latency



        # Local Fallback
        try:
            text = self._transcribe_local(pcm_bytes, lang_code)
            latency = time.time() - start_time
            logger.info(f"Local STT Completed in {latency*1000:.1f}ms")
            return text, latency
        except Exception as e:
            logger.error(f"Local STT processing error: {e}")
            return "", time.time() - start_time

