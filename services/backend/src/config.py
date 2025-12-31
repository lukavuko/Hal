import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None


def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load and cache the models.yml configuration."""
    global _config

    # ensure we only load once
    if _config is not None:
        return _config

    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "src/models.yml")

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r") as f:
        _config = yaml.safe_load(f)

    return _config


def get_ollama_config() -> Dict[str, str]:
    """Get Ollama configuration. Environment variables override config file."""
    config = load_config()
    ollama_config = config.get(
        "ollama",
        {
            "url": "http://host.docker.internal:11434",
            "vision_model": "llava:7b",
            "text_model": "llama3.2:3b",
        },
    )

    # Allow environment variable to override config file URL
    env_url = os.getenv("OLLAMA_URL")
    if env_url:
        ollama_config["url"] = env_url

    return ollama_config


def get_voice_config(voice: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific voice."""
    config = load_config()
    voices = config.get("voices", {})
    voice_config = voices.get(voice)

    if not voice_config:
        raise ValueError(
            f"Voice '{voice}' not found in config with available keys: {voices.keys()}"
        )
    return voice_config


def get_persona_prompt(voice: str) -> str:
    """Load persona prompt text file for a voice."""
    voice_config = get_voice_config(voice)
    default_config = """
        You are a focus accountability assistant. Remind the user to stay focused.
        Be firm. Be assertive. Be dramatic. Remind them what's at stake.
        Then lighten the mood by being silly from time to time.
        """
    try:
        persona_file = voice_config.get("persona_file")
        persona_path = Path("src") / persona_file
        return persona_path.read_text().strip()
    except Exception("Failed to retrieve persona prompt") as e:
        logger.error(e)
        return default_config


def get_focus_thresholds() -> Dict[str, int]:
    """Get focus score thresholds."""
    config = load_config()
    return config.get("focus", {"green_threshold": 50, "yellow_threshold": 25})


def get_default_voice() -> str:
    """Get the default voice name."""
    config = load_config()
    return config.get("default_voice", "hal")


def list_voices() -> list:
    """List all available voice names."""
    config = load_config()
    return list(config.get("voices", {}).keys())
