import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import ollama

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_focus_thresholds, get_ollama_config, get_persona_prompt

logger = logging.getLogger(__name__)


class FocusEvaluator:
    """Evaluates focus state and generates persona responses."""

    def __init__(self):
        ollama_config = get_ollama_config()
        ollama_url = ollama_config.get("url", "http://ollama:11434")
        self.text_model = ollama_config.get("text_model", "llama3.2:3b")
        self.client = ollama.Client(host=ollama_url)

        # Ensure model is available (pull if needed)
        self._ensure_model_available()

        thresholds = get_focus_thresholds()
        self.green_threshold = thresholds.get("green_threshold", 50)
        self.yellow_threshold = thresholds.get("yellow_threshold", 25)

        self.current_state = "GREEN"
        self.last_score: Optional[int] = None
        self.yellow_since: Optional[float] = None
        self.last_response_time: Optional[float] = None
        self.response_cooldown = 30  # seconds between responses

        logger.info(f"FocusEvaluator initialized (model={self.text_model})")

    def _ensure_model_available(self):
        """Check if the text model is available locally, pull if not."""
        try:
            available_models = self.client.list()
            model_names = [
                m.get("name", "") for m in available_models.get("models", [])
            ]

            # Check if our model (or a variant) is available
            base_model = self.text_model.split(":")[0]
            model_found = any(base_model in name for name in model_names)

            if not model_found:
                logger.info(f"Model '{self.text_model}' not found locally. Pulling...")
                self.client.pull(self.text_model)
                logger.info(f"Model '{self.text_model}' pulled successfully")
            else:
                logger.debug(f"Model '{self.text_model}' is available")

        except Exception as e:
            logger.warning(f"Could not verify model availability: {e}")

    def evaluate(
        self, analysis: Dict[str, Any], persona: str = "hal"
    ) -> Dict[str, Any]:
        """
        Evaluate analysis and determine if response is needed.

        Returns dict with:
        - state: GREEN/YELLOW/RED
        - response: Optional text response (only if RED and cooldown passed)
        - persona: The persona used
        """
        focus_score = analysis.get("focus_score", 50)
        observations = analysis.get("observations", "")

        self.last_score = focus_score

        # Determine new state based on score
        if focus_score >= self.green_threshold:
            new_state = "GREEN"
            self.yellow_since = None
        elif focus_score >= self.yellow_threshold:
            new_state = "YELLOW"
            if self.current_state == "GREEN":
                self.yellow_since = time.time()
        else:
            new_state = "RED"

        prev_state = self.current_state
        self.current_state = new_state

        result = {
            "state": new_state,
            "previous_state": prev_state,
            "focus_score": focus_score,
            "response": None,
            "persona": persona,
        }

        # Generate response only on RED state with cooldown
        if new_state == "RED":
            if self._should_generate_response():
                response_text = self._generate_response(observations, persona)
                result["response"] = response_text
                self.last_response_time = time.time()
                logger.info(f"Generated response for persona '{persona}'")
            else:
                logger.debug("Skipping response (cooldown active)")

        return result

    def _should_generate_response(self) -> bool:
        """Check if enough time has passed since last response."""
        if self.last_response_time is None:
            return True
        elapsed = time.time() - self.last_response_time
        return elapsed >= self.response_cooldown

    def _generate_response(self, context: str, persona: str) -> str:
        """Generate a persona-appropriate response using Ollama."""
        persona_prompt = get_persona_prompt(persona)

        full_prompt = f"""{persona_prompt}

The user appears distracted. Here's the context:
{context}

Generate ONE brief response (1-2 sentences max) to remind them to refocus. Stay in character."""

        try:
            response = self.client.generate(
                model=self.text_model,
                prompt=full_prompt,
            )

            text = response.get("response", "").strip()
            # Clean up response - take first 1-2 sentences
            sentences = text.split(".")
            if len(sentences) > 2:
                text = ".".join(sentences[:2]) + "."
            return text

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return self._fallback_response(persona)

    def _fallback_response(self, persona: str) -> str:
        """Return a fallback response if LLM fails."""
        fallbacks = {
            "hal": "I'm afraid I can't let you continue this distraction, Dave.",
            "sarcastic_friend": "Oh sure, take your time. It's not like you have work to do or anything.",
            "motivational_coach": "Hey! You've got this! Let's get back on track!",
            "drill_sergeant": "Back to work, soldier! No excuses!",
        }
        return fallbacks.get(persona, "Please return to your work.")
