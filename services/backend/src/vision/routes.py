import logging
from io import BytesIO
from pathlib import Path

from flask import Response, jsonify, request

from . import vision_bp
from .analysis import FocusAnalyzer
from .webcam import WebcamCapture

logger = logging.getLogger(__name__)

# Singleton instances
_webcam: WebcamCapture = None
_analyzer: FocusAnalyzer = None


def get_webcam() -> WebcamCapture:
    """Get or create webcam instance."""
    global _webcam
    if _webcam is None:
        _webcam = WebcamCapture()
    return _webcam


def get_analyzer() -> FocusAnalyzer:
    """Get or create analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = FocusAnalyzer()
    return _analyzer


@vision_bp.route("/capture", methods=["POST"])
def capture():
    """Capture a photo from webcam and return JPEG bytes."""
    webcam = get_webcam()

    frame = webcam.capture_frame()
    if frame is None:
        return jsonify({"error": "Failed to capture from webcam"}), 500

    # Convert PIL Image to JPEG bytes
    buf = BytesIO()
    frame.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    logger.info("Captured webcam frame")
    return Response(buf.getvalue(), mimetype="image/jpeg")


@vision_bp.route("/calibrate", methods=["POST"])
def calibrate():
    """Store calibration image from uploaded file."""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]
    image_bytes = image_file.read()

    # Save calibration image
    calibration_path = Path("/app/data/calibration.jpg")
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_bytes(image_bytes)

    # Update analyzer with calibration
    analyzer = get_analyzer()
    analyzer.set_calibration_from_bytes(image_bytes)

    logger.info("Calibration image saved and loaded")
    return jsonify({"status": "calibrated"}), 200


@vision_bp.route("/analyze", methods=["POST"])
def analyze():
    """Analyze uploaded image for focus level."""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]
    image_bytes = image_file.read()

    analyzer = get_analyzer()
    result = analyzer.analyze_from_bytes(image_bytes)

    logger.info(
        f"Analysis complete: score={result.get('focus_score')}, state={result.get('state')}"
    )
    return jsonify(result), 200
