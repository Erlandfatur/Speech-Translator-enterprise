import io
import wave
import logging
import numpy as np
from typing import Optional, Dict

logger = logging.getLogger("VirtualMicManager")
logger.setLevel(logging.INFO)

class VirtualMicManager:
    """
    Virtual Microphone Audio Router:
    Routes translated TTS audio directly into virtual audio input devices 
    (e.g., VB-Audio Virtual Cable on Windows, BlackHole on macOS).
    """
    def __init__(self):
        self.device_index: Optional[int] = None
        self.device_name: Optional[str] = None
        self.sample_rate: int = 22050
        self._detect_virtual_device()

    def _detect_virtual_device(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            keywords = ["cable", "virtual", "blackhole", "vb-audio", "stereo mix"]
            
            for idx, dev in enumerate(devices):
                name_lower = dev['name'].lower()
                # Check for output-capable audio devices matching virtual cable keywords
                if any(kw in name_lower for kw in keywords) and dev['max_output_channels'] > 0:
                    self.device_index = idx
                    self.device_name = dev['name']
                    self.sample_rate = int(dev.get('default_samplerate', 22050))
                    logger.info(f"Virtual Audio Device available: '{self.device_name}' (ID: {self.device_index}) [Standby Mode: OFF by default]")
                    return

                    
            logger.info("No Virtual Audio Cable device detected. TTS audio will play to default speakers only.")
            logger.info("To route TTS audio to Zoom/Meet microphone, install VB-Audio Cable: https://vb-audio.com/Cable/")
        except Exception as e:
            logger.warning(f"Error querying audio devices for Virtual Mic: {e}")

    def play_tts_to_virtual_mic(self, wav_bytes: bytes):
        """
        Stream WAV audio bytes into the detected Virtual Microphone device.
        """
        if not wav_bytes or len(wav_bytes) <= 44:
            return

        if self.device_index is None:
            return

        try:
            import sounddevice as sd
            
            # Read WAV bytes
            wav_io = io.BytesIO(wav_bytes)
            with wave.open(wav_io, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                frames = wf.readframes(wf.getnframes())
                
                audio_array = np.frombuffer(frames, dtype=np.int16)
                if n_channels > 1:
                    audio_array = audio_array.reshape(-1, n_channels)

            # Play to Virtual Cable device
            sd.play(audio_array, samplerate=sample_rate, device=self.device_index)
            logger.info(f"Routed {len(wav_bytes)} bytes of TTS audio to Virtual Mic '{self.device_name}'")
        except Exception as e:
            logger.error(f"Error playing TTS to Virtual Mic: {e}")
