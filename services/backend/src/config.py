import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_config: Optional[Dict[str, Any]] = None


def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load and cache the models.yml configuration."""
    global _config

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


def normalize_voice_name(voice_name: str) -> str:
    """Normalize voice name to match config keys (lowercase with underscores)."""
    return voice_name.lower().replace(" ", "_")


def get_voice_config(voice_name: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific voice."""
    config = load_config()
    voices = config.get("voices", {})
    # Normalize voice name to match config keys
    normalized = normalize_voice_name(voice_name)
    return voices.get(normalized)


def get_persona_prompt(voice_name: str) -> str:
    """Load persona prompt text file for a voice."""
    voice_config = get_voice_config(voice_name)
    if not voice_config:
        return (
            "You are a focus accountability assistant. Remind the user to stay focused."
        )

    persona_file = voice_config.get("persona_file")
    if not persona_file:
        return (
            "You are a focus accountability assistant. Remind the user to stay focused."
        )

    persona_path = Path("src") / persona_file
    if not persona_path.exists():
        return (
            "You are a focus accountability assistant. Remind the user to stay focused."
        )

    return persona_path.read_text().strip()


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
