import logging
import os
import sys
import wave
from io import BytesIO
from pathlib import Path
from typing import Dict

import requests
from piper import PiperVoice

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_default_voice, get_voice_config, list_voices

log = logging.getLogger(__name__)


class PiperTTS:
    """Text-to-speech using Piper TTS models."""

    def __init__(self):
        self.model_cache = Path(os.getenv("PIPER_CACHE", "/app/models"))
        self.model_cache.mkdir(parents=True, exist_ok=True)
        self.default_voice = get_default_voice()
        self.use_cuda = os.getenv("USE_CUDA", "false").lower() == "true"
        self.loaded_voices: Dict[str, "PiperVoice"] = {}

        log.info(f"TTS initialized (cache={self.model_cache}, cuda={self.use_cuda})")

    def _normalize_voice(self, voice: str) -> str:
        return voice.lower().replace(" ", "_")

    def _download_model(self, voice: str) -> Path:
        """Download voice model if not cached and return its path."""
        voice = self._normalize_voice(voice)
        voice_config = get_voice_config(voice)

        model_url = voice_config.get("url")
        model_path = self.model_cache / f"{voice}.onnx"
        config_path = self.model_cache / f"{voice}.onnx.json"

        # download model if not yet cached
        if not model_path.exists():
            log.info(f"Downloading model for voice '{voice}'...")
            response = requests.get(model_url, timeout=300)
            response.raise_for_status()
            model_path.write_bytes(response.content)
            log.info(f"Model downloaded: {model_path}")

        if not config_path.exists():
            log.info(f"Downloading config for voice '{voice}'...")
            response = requests.get(
                model_url.replace(".onnx", ".onnx.json"), timeout=300
            )
            response.raise_for_status()
            config_path.write_bytes(response.content)
            log.info(f"Config downloaded: {config_path}")

        return model_path

    def _load_voice(self, voice: str) -> "PiperVoice":
        """Load a voice model, downloading if needed."""
        voice = self._normalize_voice(voice)
        if voice in self.loaded_voices:
            return self.loaded_voices[voice]

        model_path = self._download_model(voice)

        log.info(f"Loading voice: {voice}")
        voice_generator = PiperVoice.load(str(model_path), use_cuda=self.use_cuda)
        self.loaded_voices[voice] = voice_generator
        log.info(f"Voice loaded: {voice}")

        return voice_generator

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

        voice = self._load_voice(voice_name)

        wav_buffer = BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        wav_buffer.seek(0)
        return wav_buffer.read()

    def list_voices(self) -> list:
        """List available voice names."""
        return list_voices()
