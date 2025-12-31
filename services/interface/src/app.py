import base64
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from api_server import get_shared_state, start_api_server, update_shared_state
from PIL import Image

CALIBRATION_PATH = Path("/app/data/calibration.jpg")
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

# Internal Docker URL for server-side API calls
BACKEND_URL = st.secrets.get("BACKEND_URL", "http://backend:5000")

# Browser-accessible URL for MJPEG stream (exposed Docker port)
STREAM_URL = st.secrets.get("STREAM_URL", "http://localhost:5000")

st.set_page_config(
    page_title="Hal - Focus Monitor", layout="wide", initial_sidebar_state="expanded"
)


def get_webcam_dimensions() -> Dict[str, int]:
    """Get webcam dimensions from backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/vision/dimensions", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return {"width": 640, "height": 480}


def initialize_session_state():
    """Initialize all session state variables."""
    if "calibrated" not in st.session_state:
        st.session_state.calibrated = CALIBRATION_PATH.exists()
    if "api_started" not in st.session_state:
        threading.Thread(target=start_api_server, daemon=True).start()
        st.session_state.api_started = True
        time.sleep(0.5)
    if "sampling_active" not in st.session_state:
        st.session_state.sampling_active = False
    if "focus_history" not in st.session_state:
        st.session_state.focus_history = []
    if "current_state" not in st.session_state:
        st.session_state.current_state = "UNKNOWN"
    if "current_score" not in st.session_state:
        st.session_state.current_score = None
    if "persona" not in st.session_state:
        st.session_state.persona = "Hal"
    if "pending_audio" not in st.session_state:
        st.session_state.pending_audio = None
    if "webcam_dims" not in st.session_state:
        st.session_state.webcam_dims = get_webcam_dimensions()
    if "calibration_image" not in st.session_state:
        st.session_state.calibration_image = None


def render_video_stream(width: int = 640, height: int = 480):
    """Render live MJPEG video stream using HTML component."""
    stream_html = f"""
    <div style="display: flex; justify-content: center;">
        <img src="{STREAM_URL}/vision/stream"
             width="{width}"
             height="{height}"
             style="border-radius: 8px; border: 2px solid #333;"
             alt="Live webcam stream" />
    </div>
    """
    components.html(stream_html, height=height + 20)


def capture_and_analyze() -> Optional[Dict]:
    """Capture a photo from vision service and analyze it."""
    try:
        # Request capture from vision service
        capture_response = requests.post(f"{BACKEND_URL}/vision/capture", timeout=10)
        if capture_response.status_code != 200:
            return None

        image_bytes = capture_response.content
        timestamp = datetime.now()

        # Send to vision service for analysis
        analyze_response = requests.post(
            f"{BACKEND_URL}/vision/analyze",
            files={"image": ("capture.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )

        if analyze_response.status_code != 200:
            return None

        analysis = analyze_response.json()

        # Get focus score and determine state
        focus_score = analysis.get("focus_score", 50)
        if focus_score >= 50:
            state = "GREEN"
        elif focus_score >= 25:
            state = "YELLOW"
        else:
            state = "RED"

        st.session_state.current_state = state
        st.session_state.current_score = focus_score

        # Add to focus history
        st.session_state.focus_history.append(
            {"timestamp": timestamp, "score": focus_score}
        )

        # Keep only last 100 entries
        if len(st.session_state.focus_history) > 100:
            st.session_state.focus_history = st.session_state.focus_history[-100:]

        # Update shared state for API
        update_shared_state(
            {
                "state": state,
                "latest_analysis": analysis,
                "focus_score": focus_score,
            }
        )

        # If RED state, trigger mind service for response
        if state == "RED":
            trigger_mind_response(analysis)

        return analysis

    except requests.exceptions.RequestException:
        return None


def trigger_mind_response(analysis: Dict):
    """Trigger the mind service to generate a response when user is distracted."""
    try:
        mind_response = requests.post(
            f"{BACKEND_URL}/mind/evaluate",
            json={"analysis": analysis, "persona": st.session_state.persona},
            timeout=15,
        )

        if mind_response.status_code == 200:
            result = mind_response.json()
            response_text = result.get("response", "")

            if response_text:
                # Send to speech service and capture audio
                speech_response = requests.post(
                    f"{BACKEND_URL}/speech/speak",
                    json={"text": response_text, "persona": st.session_state.persona},
                    timeout=30,
                )

                if speech_response.status_code == 200:
                    st.session_state.pending_audio = speech_response.content

                update_shared_state({"last_response": response_text})

    except requests.exceptions.RequestException:
        pass


def calibration_wizard():
    """Display the calibration wizard for first-time setup."""
    st.title("Hal Calibration Wizard")
    st.markdown("### Welcome! Let's calibrate your focused workspace.")
    st.info(
        "Position yourself at your desk in a focused posture. Hal will use this as the baseline."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Live Camera Feed")
        dims = st.session_state.webcam_dims
        render_video_stream(width=dims["width"], height=dims["height"])

        if st.button(
            "Capture Calibration Image", type="primary", use_container_width=True
        ):
            try:
                response = requests.post(f"{BACKEND_URL}/vision/capture", timeout=10)
                if response.status_code == 200:
                    img_data = response.content
                    CALIBRATION_PATH.write_bytes(img_data)

                    # Store for display
                    st.session_state.calibration_image = img_data

                    # Send to vision service to store as reference
                    requests.post(
                        f"{BACKEND_URL}/vision/calibrate",
                        files={"image": ("calibration.jpg", img_data, "image/jpeg")},
                        timeout=10,
                    )

                    st.success("Calibration image captured! Review it on the right.")
                else:
                    st.error(f"Failed to capture: {response.text}")
            except Exception as e:
                st.error(f"Cannot connect to vision service: {e}")

    with col2:
        st.subheader("Calibration Image")

        # Show captured calibration image
        if st.session_state.calibration_image:
            img = Image.open(BytesIO(st.session_state.calibration_image))
            st.image(
                img, caption="Captured Calibration Image", use_container_width=True
            )

            col_confirm, col_retry = st.columns(2)
            with col_confirm:
                if st.button(
                    "Confirm & Start", type="primary", use_container_width=True
                ):
                    st.session_state.calibrated = True
                    st.rerun()
            with col_retry:
                if st.button("Retake", use_container_width=True):
                    st.session_state.calibration_image = None
                    st.rerun()
        elif CALIBRATION_PATH.exists():
            st.image(
                str(CALIBRATION_PATH),
                caption="Previous Calibration",
                use_container_width=True,
            )
            if st.button("Use This & Start", type="primary", use_container_width=True):
                st.session_state.calibrated = True
                st.rerun()
        else:
            st.info("Capture an image from the live feed to set your calibration.")


def render_focus_chart():
    """Render the focus score line chart."""
    if not st.session_state.focus_history:
        st.info("Focus history will appear here once sampling begins.")
        return

    history = st.session_state.focus_history
    timestamps = [h["timestamp"].strftime("%H:%M:%S") for h in history]
    scores = [h["score"] for h in history]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=scores,
            mode="lines+markers",
            name="Focus Score",
            line=dict(color="#00cc00", width=2),
            marker=dict(size=6),
        )
    )

    fig.add_hline(
        y=50, line_dash="dash", line_color="yellow", annotation_text="Yellow threshold"
    )
    fig.add_hline(
        y=25, line_dash="dash", line_color="red", annotation_text="Red threshold"
    )

    fig.update_layout(
        title="Focus Score Over Time",
        xaxis_title="Time",
        yaxis_title="Focus Score",
        yaxis=dict(range=[0, 100]),
        height=300,
        margin=dict(l=50, r=50, t=50, b=50),
    )

    st.plotly_chart(fig, use_container_width=True)


def main_dashboard():
    """Main dashboard UI."""
    st.title("Hal - Focus Accountability Monitor")

    # Top row: Status and controls
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        state = st.session_state.current_state
        state_colors = {
            "GREEN": ":green[GREEN]",
            "YELLOW": ":orange[YELLOW]",
            "RED": ":red[RED]",
            "UNKNOWN": "UNKNOWN",
        }
        state_icons = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴", "UNKNOWN": "⚪"}

        score_text = (
            f" ({st.session_state.current_score}%)"
            if st.session_state.current_score is not None
            else ""
        )
        st.markdown(
            f"## Status: {state_icons.get(state, '⚪')} {state_colors.get(state, state)}{score_text}"
        )

    with col2:
        shared_state = get_shared_state()
        st.metric("Uptime", shared_state.get("uptime", "00:00:00"))

    with col3:
        if st.session_state.sampling_active:
            if st.button("Stop Sampling", type="secondary", use_container_width=True):
                st.session_state.sampling_active = False
                update_shared_state({"sampling_active": False})
                st.rerun()
        else:
            if st.button("Start Sampling", type="primary", use_container_width=True):
                st.session_state.sampling_active = True
                update_shared_state({"sampling_active": True})
                st.rerun()

    with col4:
        if st.button("Recalibrate", use_container_width=True):
            CALIBRATION_PATH.unlink(missing_ok=True)
            st.session_state.calibrated = False
            st.session_state.calibration_image = None
            st.rerun()

    # Sampling status indicator
    if st.session_state.sampling_active:
        st.success("Sampling ACTIVE - Analyzing every 10 seconds")
    else:
        st.warning("Sampling PAUSED - Click 'Start Sampling' to begin monitoring")

    st.divider()

    # Main content area
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.subheader("Live Webcam Feed")
        dims = st.session_state.webcam_dims
        render_video_stream(width=dims["width"], height=dims["height"])

        # Focus Analysis section
        st.subheader("Focus Analysis")
        analysis = shared_state.get("latest_analysis", {})
        if analysis:
            st.write(f"**Observations:** {analysis.get('observations', 'None')}")
        else:
            st.info("No analysis yet. Start sampling to begin monitoring.")

    with col_side:
        # Persona selection
        with st.expander("Settings", expanded=True):
            personas = [
                "Hal",
                "Sarcastic Friend",
                "Motivational Coach",
                "Drill Sergeant",
            ]
            selected_persona = st.selectbox(
                "Voice Character",
                personas,
                index=(
                    personas.index(st.session_state.persona)
                    if st.session_state.persona in personas
                    else 0
                ),
            )

            if selected_persona != st.session_state.persona:
                st.session_state.persona = selected_persona
                update_shared_state({"persona": selected_persona})
                st.success(f"Switched to {selected_persona}")

            if st.button("Test Audio", use_container_width=True):
                try:
                    speech_response = requests.post(
                        f"{BACKEND_URL}/speech/speak",
                        json={
                            "text": "Audio test successful. I am watching you.",
                            "persona": st.session_state.persona,
                        },
                        timeout=30,
                    )
                    if speech_response.status_code == 200:
                        st.session_state.pending_audio = speech_response.content
                        st.success("Audio ready!")
                    else:
                        st.error(f"Speech service error: {speech_response.text}")
                except Exception as e:
                    st.error(f"Speech service unavailable: {e}")

        # Event Log
        st.subheader("Event Log")
        events: List[Dict] = shared_state.get("events", [])
        if events:
            for event in reversed(events[-10:]):
                timestamp = event.get("timestamp", "")
                message = event.get("message", "")
                st.text(f"[{timestamp}] {message}")
        else:
            st.info("No events yet...")

        # Last Response
        if shared_state.get("last_response"):
            st.subheader("Last Response")
            st.info(shared_state["last_response"])

        # Audio Player
        if st.session_state.pending_audio:
            st.subheader("Audio Response")
            st.audio(st.session_state.pending_audio, format="audio/wav", autoplay=True)
            st.session_state.pending_audio = None

    st.divider()

    # Focus History Chart
    st.subheader("Focus History")
    render_focus_chart()

    # Auto-analyze when sampling is active (stream handles display)
    if st.session_state.sampling_active:
        with st.spinner("Analyzing..."):
            capture_and_analyze()
        time.sleep(10)
        st.rerun()


# Initialize
initialize_session_state()

# Route to appropriate view
if not st.session_state.calibrated:
    calibration_wizard()
else:
    main_dashboard()

st.markdown("---")
st.caption("Hal - Local Focus Accountability Agent")
