import os
import io
import time
import logging
import wave
from typing import Tuple
from piper import PiperVoice

from pipeline.edge_tts_engine import EdgeTTSEngine

logger = logging.getLogger("TTSEngine")
logger.setLevel(logging.INFO)

class StreamingTTS:
    """
    Hybrid Text-to-Speech Engine:
    - Primary: Microsoft Edge Neural TTS (ultra-realistic human voice).
    - Fallback: Piper TTS (fully offline ONNX model).
    """
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)
        self.edge_tts = EdgeTTSEngine()
        
        # Define paths to Piper ONNX models
        self.voices = {
            "en": os.path.join(self.models_dir, "en_US-lessac-medium.onnx"),
            "id": os.path.join(self.models_dir, "id_ID-news_tts-medium.onnx")
        }
        
        self.loaded_voices = {}
        
        for lang, path in self.voices.items():
            if os.path.exists(path):
                logger.info(f"Loading fallback Piper voice for '{lang}' from {path}...")
                self.loaded_voices[lang] = PiperVoice.load(path)
            else:
                logger.warning(f"Piper voice model not found for '{lang}' at {path}.")

        self.is_loaded = True

    def synthesize(self, text: str, target_lang: str = "id", sample_rate: int = 16000) -> Tuple[bytes, float]:
        """
        Synthesize input text using Edge-TTS Neural voice with Piper ONNX fallback.
        """
        start_time = time.time()
        if not text or not text.strip():
            return b"", 0.0

        lang_code = "id" if target_lang.lower().startswith("id") else "en"

        # 1. Try Microsoft Edge Neural TTS first
        audio_bytes, latency = self.edge_tts.synthesize(text.strip(), lang_code)
        if audio_bytes and len(audio_bytes) > 0:
            return audio_bytes, latency

        # 2. Fallback to Piper ONNX local voice
        if lang_code in self.loaded_voices:
            try:
                voice = self.loaded_voices[lang_code]
                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wav_file:
                    if hasattr(voice, "synthesize_wav"):
                        voice.synthesize_wav(text.strip(), wav_file)
                    else:
                        for chunk in voice.synthesize(text.strip()):
                            if hasattr(chunk, "audio_bytes"):
                                wav_file.writeframes(chunk.audio_bytes)
                            elif isinstance(chunk, bytes):
                                wav_file.writeframes(chunk)
                
                wav_bytes = wav_io.getvalue()
                latency = time.time() - start_time
                logger.info(f"Piper TTS Fallback Completed for '{lang_code}' ({len(wav_bytes)} bytes) in {latency*1000:.1f}ms")
                return wav_bytes, latency
            except Exception as e:
                logger.error(f"Error during Piper TTS synthesis: {e}")

        return b"", time.time() - start_time


