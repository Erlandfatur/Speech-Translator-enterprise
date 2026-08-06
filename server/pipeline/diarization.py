import numpy as np
import logging
from typing import Dict

logger = logging.getLogger("SpeakerDiarizer")
logger.setLevel(logging.INFO)

class SpeakerDiarizer:
    """
    Lightweight Real-time Speaker Diarization Engine:
    Clusters spectral audio signatures to identify distinct speaker voices in meeting rooms.
    """
    def __init__(self, max_speakers: int = 4):
        self.max_speakers = max_speakers
        self.speaker_profiles: Dict[int, float] = {}
        self.speaker_count = 0

    def _extract_feature(self, pcm_bytes: bytes) -> float:
        """Extract spectral centroid feature from PCM audio bytes."""
        if not pcm_bytes or len(pcm_bytes) < 512:
            return 0.0
        
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        # Compute zero crossing rate and mean absolute amplitude as signature
        zcr = np.mean(np.abs(np.diff(np.sign(audio))))
        amplitude = np.mean(np.abs(audio))
        return float(zcr * 100.0 + amplitude)

    def identify_speaker(self, pcm_bytes: bytes, default_label: str = "Speaker 1") -> str:
        """
        Returns assigned speaker label (e.g. 'Pembicara 1', 'Pembicara 2') based on audio features.
        """
        if not pcm_bytes or len(pcm_bytes) < 1000:
            return default_label

        try:
            feat = self._extract_feature(pcm_bytes)
            if feat == 0.0:
                return default_label

            # Match against existing speaker profiles
            best_id = None
            min_dist = float('inf')

            for spk_id, profile_feat in self.speaker_profiles.items():
                dist = abs(feat - profile_feat)
                if dist < min_dist:
                    min_dist = dist
                    best_id = spk_id

            # Threshold for assigning to existing vs creating new speaker profile
            if best_id is not None and min_dist < 450.0:
                # Update running average profile
                self.speaker_profiles[best_id] = 0.8 * self.speaker_profiles[best_id] + 0.2 * feat
                return f"Pembicara {best_id}"

            if self.speaker_count < self.max_speakers:
                self.speaker_count += 1
                self.speaker_profiles[self.speaker_count] = feat
                return f"Pembicara {self.speaker_count}"

            return f"Pembicara {best_id if best_id else 1}"
        except Exception as e:
            logger.warning(f"Diarization error: {e}")
            return default_label
