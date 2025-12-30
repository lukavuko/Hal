import logging

from flask import Response, jsonify, request

from . import speech_bp
from .text2speech import PiperTTS

logger = logging.getLogger(__name__)

# Singleton instance
_tts: PiperTTS = None


def get_tts() -> PiperTTS:
    """Get or create TTS instance."""
    global _tts
    if _tts is None:
        _tts = PiperTTS()
    return _tts


@speech_bp.route("/speak", methods=["POST"])
def speak():
    """Convert text to speech and return WAV audio bytes."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    text = data.get("text")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    persona = data.get("persona", "hal")

    tts = get_tts()

    try:
        audio_bytes = tts.synthesize(text, persona)
        logger.info(
            f"Synthesized speech for persona '{persona}': {len(audio_bytes)} bytes"
        )
        return Response(audio_bytes, mimetype="audio/wav")

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        return jsonify({"error": str(e)}), 500


@speech_bp.route("/voices", methods=["GET"])
def list_voices():
    """List available voices."""
    tts = get_tts()
    return jsonify({"voices": tts.list_voices(), "default": tts.default_voice}), 200
