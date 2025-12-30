import os
import threading
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request

app = Flask(__name__)

_shared_state: Dict[str, Any] = {
    "state": "UNKNOWN",
    "uptime": "00:00:00",
    "latest_image": None,
    "latest_analysis": {},
    "persona": "Hal",
    "events": [],
    "last_response": None,
    "start_time": datetime.now(),
    "sampling_active": False,
    "focus_score": None,
    "focus_history": [],
}
_state_lock = threading.Lock()


def get_shared_state() -> Dict[str, Any]:
    """Get a copy of the current shared state."""
    with _state_lock:
        uptime_delta = datetime.now() - _shared_state["start_time"]
        hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        _shared_state["uptime"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return _shared_state.copy()


def update_shared_state(updates: Dict[str, Any]) -> None:
    """Update the shared state with new values."""
    with _state_lock:
        for key, value in updates.items():
            if key in _shared_state:
                _shared_state[key] = value

        # Log state changes
        if "state" in updates:
            timestamp = datetime.now().strftime("%H:%M:%S")
            event = {
                "timestamp": timestamp,
                "message": f"State changed to {updates['state']}",
            }
            _shared_state["events"].append(event)
            if len(_shared_state["events"]) > 100:
                _shared_state["events"] = _shared_state["events"][-100:]


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/state", methods=["GET"])
def get_state():
    """Get the current application state."""
    return jsonify(get_shared_state()), 200


@app.route("/status", methods=["POST"])
def update_status():
    data = request.json
    with _state_lock:
        if "state" in data:
            _shared_state["state"] = data["state"]
        if "analysis" in data:
            _shared_state["latest_analysis"] = data["analysis"]
        if "image" in data:
            _shared_state["latest_image"] = data["image"]
        if "focus_score" in data:
            _shared_state["focus_score"] = data["focus_score"]

    timestamp = datetime.now().strftime("%H:%M:%S")
    event = {
        "timestamp": timestamp,
        "message": f"State changed to {data.get('state', 'UNKNOWN')}",
    }

    with _state_lock:
        _shared_state["events"].append(event)
        if len(_shared_state["events"]) > 100:
            _shared_state["events"] = _shared_state["events"][-100:]

    return jsonify({"status": "ok"}), 200


@app.route("/log", methods=["POST"])
def add_log():
    data = request.json
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = data.get("message", "")

    event = {"timestamp": timestamp, "message": message}

    with _state_lock:
        _shared_state["events"].append(event)
        if len(_shared_state["events"]) > 100:
            _shared_state["events"] = _shared_state["events"][-100:]

        if "response" in data:
            _shared_state["last_response"] = data["response"]

    return jsonify({"status": "ok"}), 200


@app.route("/focus-history", methods=["GET"])
def get_focus_history():
    """Get the focus score history."""
    with _state_lock:
        return jsonify(_shared_state.get("focus_history", [])), 200


@app.route("/focus-history", methods=["POST"])
def add_focus_history():
    """Add a focus score entry to history."""
    data = request.json
    timestamp = data.get("timestamp", datetime.now().isoformat())
    score = data.get("score", 0)

    entry = {"timestamp": timestamp, "score": score}

    with _state_lock:
        _shared_state["focus_history"].append(entry)
        if len(_shared_state["focus_history"]) > 100:
            _shared_state["focus_history"] = _shared_state["focus_history"][-100:]

    return jsonify({"status": "ok"}), 200


@app.route("/calibration", methods=["GET"])
def get_calibration():
    from pathlib import Path

    cal_path = Path("/app/data/calibration.jpg")
    if cal_path.exists():
        return cal_path.read_bytes(), 200, {"Content-Type": "image/jpeg"}
    return jsonify({"error": "No calibration image"}), 404


@app.route("/calibration", methods=["POST"])
def save_calibration():
    from pathlib import Path

    cal_path = Path("/app/data/calibration.jpg")
    cal_path.write_bytes(request.data)
    return jsonify({"status": "saved"}), 200


def start_api_server():
    port = int(os.getenv("API_PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
