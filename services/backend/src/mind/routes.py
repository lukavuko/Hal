import logging

from flask import jsonify, request

from . import mind_bp
from .evaluator import FocusEvaluator

logger = logging.getLogger(__name__)

# Singleton instance
_evaluator: FocusEvaluator = None


def get_evaluator() -> FocusEvaluator:
    """Get or create evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = FocusEvaluator()
    return _evaluator


@mind_bp.route("/evaluate", methods=["POST"])
def evaluate():
    """Evaluate focus analysis and generate response if needed."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    analysis = data.get("analysis", {})
    persona = data.get("persona", "hal")

    evaluator = get_evaluator()
    result = evaluator.evaluate(analysis, persona)

    logger.info(
        f"Evaluation: state={result.get('state')}, response_generated={result.get('response') is not None}"
    )
    return jsonify(result), 200


@mind_bp.route("/state", methods=["GET"])
def get_state():
    """Get current focus state without triggering evaluation."""
    evaluator = get_evaluator()
    return (
        jsonify({"state": evaluator.current_state, "last_score": evaluator.last_score}),
        200,
    )
