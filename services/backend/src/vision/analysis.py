import base64
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_focus_thresholds, get_ollama_config

logger = logging.getLogger(__name__)


class FocusAnalyzer:
    """Analyzes images using Ollama multimodal LLM to determine focus level."""

    def __init__(self):
        ollama_config = get_ollama_config()
        self.ollama_url = ollama_config.get("url", "http://host.docker.internal:11434")
        self.vision_model = ollama_config.get("vision_model", "llava:7b")

        thresholds = get_focus_thresholds()
        self.green_threshold = thresholds.get("green_threshold", 50)
        self.yellow_threshold = thresholds.get("yellow_threshold", 25)

        self.calibration_description: Optional[str] = None
        self._load_existing_calibration()

        logger.info(f"FocusAnalyzer initialized (model={self.vision_model})")

    def _load_existing_calibration(self):
        """Load calibration from disk if exists."""
        calibration_path = Path("/app/data/calibration.jpg")
        if calibration_path.exists():
            try:
                image_bytes = calibration_path.read_bytes()
                self.set_calibration_from_bytes(image_bytes)
                logger.info("Loaded existing calibration")
            except Exception as e:
                logger.warning(f"Failed to load calibration: {e}")

    def set_calibration_from_bytes(self, image_bytes: bytes):
        """Analyze calibration image and store description."""
        self.calibration_description = self._describe_image(image_bytes)
        logger.info(f"Calibration set: {self.calibration_description[:100]}...")

    def _image_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def _describe_image(self, image_bytes: bytes) -> str:
        """Get a description of the image from Ollama."""
        prompt = """Describe this image briefly. Focus on:
- Is there a person visible?
- What is their posture and position?
- Are they at a desk/workstation?
- What are they doing (working, looking at phone, away, etc.)?
Keep response under 50 words."""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [self._image_to_base64(image_bytes)],
                    "stream": False,
                },
                timeout=60,
            )

            if response.status_code == 200:
                return response.json().get("response", "").strip()
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return "Unable to analyze image"

        except Exception as e:
            logger.error(f"Failed to describe image: {e}")
            return "Unable to analyze image"

    def analyze_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """Analyze image and return focus assessment."""
        if self.calibration_description is None:
            return {
                "focus_score": 0,
                "state": "RED",
                "observations": "No calibration baseline set. Please calibrate first.",
                "focused": False,
            }

        # Build analysis prompt
        prompt = f"""You are analyzing a webcam image to determine if a person is focused on their work.

CALIBRATION BASELINE (what focused looks like):
{self.calibration_description}

TASK: Compare the current image to the baseline and rate focus from 0-100.

Scoring guide:
- 90-100: Person in same focused position as baseline
- 70-89: Person at desk, minor posture differences
- 50-69: Person present but attention may be divided
- 25-49: Person distracted (phone, looking away, different activity)
- 0-24: Person not at desk or major scene change

Respond with ONLY a JSON object in this exact format:
{{"focus_score": <number 0-100>, "observations": "<brief reason>"}}"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [self._image_to_base64(image_bytes)],
                    "stream": False,
                },
                timeout=60,
            )

            if response.status_code == 200:
                result_text = response.json().get("response", "").strip()
                return self._parse_analysis(result_text)
            else:
                logger.error(f"Ollama analysis error: {response.status_code}")
                return self._default_response("Ollama service error")

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return self._default_response(f"Analysis error: {str(e)}")

    def _parse_analysis(self, result_text: str) -> Dict[str, Any]:
        """Parse LLM response into structured result."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[^}]+\}", result_text)
            if json_match:
                data = json.loads(json_match.group())
                focus_score = int(data.get("focus_score", 50))
                observations = data.get("observations", "No details provided")
            else:
                # Fallback: try to find a number
                numbers = re.findall(r"\b(\d{1,3})\b", result_text)
                focus_score = int(numbers[0]) if numbers else 50
                observations = result_text[:200]

            # Clamp score
            focus_score = max(0, min(100, focus_score))

            # Determine state
            if focus_score >= self.green_threshold:
                state = "GREEN"
            elif focus_score >= self.yellow_threshold:
                state = "YELLOW"
            else:
                state = "RED"

            return {
                "focus_score": focus_score,
                "state": state,
                "observations": observations,
                "focused": focus_score >= self.green_threshold,
            }

        except Exception as e:
            logger.warning(f"Failed to parse analysis: {e}")
            return self._default_response("Failed to parse analysis")

    def _default_response(self, reason: str) -> Dict[str, Any]:
        """Return default response on error."""
        return {
            "focus_score": 50,
            "state": "YELLOW",
            "observations": reason,
            "focused": False,
        }
