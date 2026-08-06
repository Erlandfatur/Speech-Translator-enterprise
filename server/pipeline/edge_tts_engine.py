import io
import time
import asyncio
import logging
from typing import Tuple, Optional

logger = logging.getLogger("EdgeTTSEngine")
logger.setLevel(logging.INFO)

VOICE_MAP = {
    "id": "id-ID-ArdiNeural",         # Indonesian
    "en": "en-US-ChristopherNeural",   # English
    "ja": "ja-JP-NanamiNeural",        # Japanese
    "ko": "ko-KR-SunHiNeural",         # Korean
    "zh": "zh-CN-XiaoxiaoNeural",      # Mandarin Chinese
    "es": "es-ES-AlvaroNeural",        # Spanish
    "fr": "fr-FR-HenriNeural",         # French
    "de": "de-DE-KillianNeural",       # German
    "ar": "ar-SA-HamedNeural",         # Arabic
    "ru": "ru-RU-DmitryNeural"         # Russian
}



class EdgeTTSEngine:
    """
    Microsoft Edge Neural TTS Engine:
    Generates ultra-realistic human-like neural voices for Indonesian and English.
    """
    def __init__(self):
        logger.info("EdgeTTSEngine initialized successfully (Microsoft Neural Voices).")

    async def _async_synthesize(self, text: str, voice_name: str) -> bytes:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice_name)
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        return bytes(audio_data)

    def synthesize(self, text: str, target_lang: str = "id") -> Tuple[Optional[bytes], float]:
        """
        Synthesizes text into high-quality audio bytes using Microsoft Edge Neural TTS.
        """
        start_time = time.time()
        if not text or not text.strip():
            return None, 0.0

        lang_key = "en" if target_lang.lower().startswith("en") else target_lang.lower()[:2]
        voice_name = VOICE_MAP.get(lang_key, "id-ID-ArdiNeural")

        try:
            audio_bytes = asyncio.run(self._async_synthesize(text.strip(), voice_name))
            latency = time.time() - start_time
            logger.info(f"Edge-TTS Completed for '{lang_key}' ({voice_name}, {len(audio_bytes)} bytes) in {latency*1000:.1f}ms")
            return audio_bytes, latency
        except Exception as e:
            logger.warning(f"Edge-TTS synthesis error: {e}")
            return None, time.time() - start_time

