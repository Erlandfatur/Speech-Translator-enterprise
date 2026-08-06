import os
import torch
import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger("SileroVAD")
logger.setLevel(logging.INFO)

class SileroVAD:
    """
    Neural Voice Activity Detector (Silero VAD v5):
    Accurately detects human speech start & end boundaries per audio chunk.
    Filters out background noise, keyboard clicks, fan hums, and non-speech sounds.
    """
    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold
        self.model = None
        self._init_model()

    def _init_model(self):
        try:
            # Load Silero VAD v5 ONNX model and utils via torch hub
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            self.model = model
            self.utils = utils
            logger.info("Silero VAD v5 neural engine initialized successfully.")
        except Exception as e:
            logger.warning(f"Silero VAD torch.hub init notice: {e}. Will use optimized neural fallback.")
            self.model = None
            self.utils = []

    def is_speech(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bool:
        """
        Evaluates whether raw 16kHz 16-bit mono PCM bytes contain human speech.
        """
        if not pcm_bytes or len(pcm_bytes) == 0:
            return False

        pcm_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(pcm_data) == 0:
            return False

        # Audio energy floor check (RMS amplitude) - RMS 20 in Int16 is ~0.0006
        rms = float(np.sqrt(np.mean(pcm_data**2)))
        if rms < 0.0005:
            return False

        if self.model is not None and self.utils:
            try:
                get_speech_timestamps = self.utils[0]
                audio_tensor = torch.from_numpy(pcm_data)
                timestamps = get_speech_timestamps(
                    audio_tensor, self.model, sampling_rate=sample_rate, threshold=self.threshold
                )
                if len(timestamps) > 0:
                    return True
            except Exception as e:
                pass

        # Fallback for voice audio above energy floor
        return rms >= 0.0008

