import logging
import os
import sys
import wave
from io import BytesIO
from pathlib import Path
from typing import Dict

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_default_voice, get_voice_config
from config import list_voices as config_list_voices

logger = logging.getLogger(__name__)

try:
    from piper import PiperVoice

    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    logger.warning("Piper not available")


class PiperTTS:
    """Text-to-speech using Piper TTS models."""

    def __init__(self):
        self.model_cache = Path(os.getenv("PIPER_CACHE", "/app/models"))
        self.model_cache.mkdir(parents=True, exist_ok=True)

        self.default_voice = get_default_voice()
        self.use_cuda = os.getenv("USE_CUDA", "false").lower() == "true"

        self.loaded_voices: Dict[str, "PiperVoice"] = {}

        logger.info(
            f"PiperTTS initialized (cache={self.model_cache}, cuda={self.use_cuda})"
        )

    def _download_model(self, voice_name: str) -> tuple[Path, Path]:
        """Download voice model if not cached."""
        voice_config = get_voice_config(voice_name)
        if not voice_config:
            raise ValueError(f"Voice '{voice_name}' not found in config")

        model_url = voice_config.get("url")
        config_url = voice_config.get("config_url")

        if not model_url or not config_url:
            raise ValueError(f"Voice '{voice_name}' missing url or config_url")

        model_path = self.model_cache / f"{voice_name}.onnx"
        config_path = self.model_cache / f"{voice_name}.onnx.json"

        if not model_path.exists():
            logger.info(f"Downloading model for voice '{voice_name}'...")
            response = requests.get(model_url, timeout=300)
            response.raise_for_status()
            model_path.write_bytes(response.content)
            logger.info(f"Model downloaded: {model_path}")

        if not config_path.exists():
            logger.info(f"Downloading config for voice '{voice_name}'...")
            response = requests.get(config_url, timeout=60)
            response.raise_for_status()
            config_path.write_bytes(response.content)
            logger.info(f"Config downloaded: {config_path}")

        return model_path, config_path

    def _load_voice(self, voice_name: str) -> "PiperVoice":
        """Load a voice model, downloading if needed."""
        if voice_name in self.loaded_voices:
            return self.loaded_voices[voice_name]

        if not PIPER_AVAILABLE:
            raise RuntimeError("Piper library not available")

        model_path, _ = self._download_model(voice_name)

        logger.info(f"Loading voice: {voice_name}")
        voice = PiperVoice.load(str(model_path), use_cuda=self.use_cuda)

        self.loaded_voices[voice_name] = voice
        logger.info(f"Voice loaded: {voice_name}")

        return voice

    def synthesize(self, text: str, voice_name: str = None) -> bytes:
        """
        Synthesize text to speech and return WAV bytes.

        Args:
            text: Text to synthesize
            voice_name: Voice/persona name (defaults to config default)

        Returns:
            WAV audio bytes
        """
        if voice_name is None:
            voice_name = self.default_voice

        # Normalize voice name (interface may send "Hal" but config has "hal")
        voice_name = voice_name.lower().replace(" ", "_")

        voice = self._load_voice(voice_name)

        # Synthesize to in-memory WAV
        wav_buffer = BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        wav_buffer.seek(0)
        return wav_buffer.read()

    def list_voices(self) -> list:
        """List available voice names."""
        return config_list_voices()
