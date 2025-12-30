"""
Hal Backend - Focus Accountability Service

A single Flask application hosting vision, mind, and speech modules
for the Hal focus accountability system.
"""

import logging
import os
from pathlib import Path

from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Ensure data directory exists
    data_dir = Path("/app/data")
    data_dir.mkdir(parents=True, exist_ok=True)

    # Ensure models directory exists
    models_dir = Path(os.getenv("PIPER_CACHE", "/app/models"))
    models_dir.mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from mind import mind_bp
    from speech import speech_bp
    from vision import vision_bp

    app.register_blueprint(vision_bp)
    app.register_blueprint(mind_bp)
    app.register_blueprint(speech_bp)

    # Root health check
    @app.route("/health", methods=["GET"])
    def health():
        """Aggregated health check for all services."""
        return (
            jsonify(
                {
                    "status": "healthy",
                    "services": {"vision": "ok", "mind": "ok", "speech": "ok"},
                }
            ),
            200,
        )

    @app.route("/", methods=["GET"])
    def root():
        """Root endpoint with API info."""
        return (
            jsonify(
                {
                    "service": "Hal Backend",
                    "version": "1.0.0",
                    "endpoints": {
                        "vision": [
                            "/vision/capture",
                            "/vision/calibrate",
                            "/vision/analyze",
                        ],
                        "mind": ["/mind/evaluate", "/mind/state"],
                        "speech": ["/speech/speak", "/speech/voices"],
                    },
                }
            ),
            200,
        )

    logger.info("Hal Backend initialized")
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    logger.info(f"Starting Hal Backend on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
