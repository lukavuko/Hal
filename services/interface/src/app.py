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
from api_server import get_shared_state, start_api_server, update_shared_state
from PIL import Image

CALIBRATION_PATH = Path("/app/data/calibration.jpg")
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://backend:5000")

st.set_page_config(
    page_title="Hal - Focus Monitor", layout="wide", initial_sidebar_state="expanded"
)


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
        st.session_state.focus_history = (
            []
        )  # List of {"timestamp": datetime, "score": int}
    if "latest_image_b64" not in st.session_state:
        st.session_state.latest_image_b64 = None
    if "latest_timestamp" not in st.session_state:
        st.session_state.latest_timestamp = None
    if "current_state" not in st.session_state:
        st.session_state.current_state = "UNKNOWN"
    if "current_score" not in st.session_state:
        st.session_state.current_score = None
    if "persona" not in st.session_state:
        st.session_state.persona = "Hal"
    if "pending_audio" not in st.session_state:
        st.session_state.pending_audio = None  # WAV bytes to play


def capture_and_analyze() -> Optional[Dict]:
    """Capture a photo from vision service and analyze it."""
    try:
        # Request capture from vision service
        capture_response = requests.post(f"{BACKEND_URL}/vision/capture", timeout=10)
        if capture_response.status_code != 200:
            st.error(f"Capture failed: {capture_response.text}")
            return None

        # Store the image
        image_bytes = capture_response.content
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        timestamp = datetime.now()

        st.session_state.latest_image_b64 = image_b64
        st.session_state.latest_timestamp = timestamp

        # Send to vision service for analysis
        analyze_response = requests.post(
            f"{BACKEND_URL}/vision/analyze",
            files={"image": ("capture.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )

        if analyze_response.status_code != 200:
            st.warning(f"Analysis failed: {analyze_response.text}")
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
                "latest_image": image_b64,
                "latest_analysis": analysis,
                "focus_score": focus_score,
            }
        )

        # If RED state, trigger mind service for response
        if state == "RED":
            trigger_mind_response(analysis)

        return analysis

    except requests.exceptions.RequestException as e:
        st.error(f"Service communication error: {e}")
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
                    # Store audio bytes for playback
                    st.session_state.pending_audio = speech_response.content

                # Log the response
                update_shared_state({"last_response": response_text})

    except requests.exceptions.RequestException as e:
        st.warning(f"Mind service error: {e}")


def calibration_wizard():
    """Display the calibration wizard for first-time setup."""
    st.title("Hal Calibration Wizard")
    st.markdown("### Welcome! Let's calibrate your focused workspace.")
    st.info(
        "Position yourself at your desk in a focused posture. Hal will use this as the baseline."
    )

    col1, col2 = st.columns(2)

    with col1:
        # Preview button
        if st.button("Preview Camera", use_container_width=True):
            try:
                response = requests.post(f"{BACKEND_URL}/vision/capture", timeout=10)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    st.image(img, caption="Camera Preview", use_container_width=True)
                else:
                    st.error(f"Failed to get preview: {response.text}")
            except Exception as e:
                st.error(f"Cannot connect to vision service: {e}")

        if st.button(
            "Capture Calibration Image", type="primary", use_container_width=True
        ):
            try:
                response = requests.post(f"{BACKEND_URL}/vision/capture", timeout=10)
                if response.status_code == 200:
                    img_data = response.content
                    CALIBRATION_PATH.write_bytes(img_data)

                    # Also send to vision service to store as reference
                    requests.post(
                        f"{BACKEND_URL}/vision/calibrate",
                        files={"image": ("calibration.jpg", img_data, "image/jpeg")},
                        timeout=10,
                    )

                    st.success("Calibration successful!")
                    time.sleep(1)
                    st.session_state.calibrated = True
                    st.rerun()
                else:
                    st.error(f"Failed to capture: {response.text}")
            except Exception as e:
                st.error(f"Cannot connect to vision service: {e}")

    with col2:
        if CALIBRATION_PATH.exists():
            st.image(
                str(CALIBRATION_PATH),
                caption="Current Calibration",
                use_container_width=True,
            )


def render_focus_chart():
    """Render the focus score line chart."""
    if not st.session_state.focus_history:
        st.info("Focus history will appear here once sampling begins.")
        return

    history = st.session_state.focus_history
    timestamps = [h["timestamp"].strftime("%H:%M:%S") for h in history]
    scores = [h["score"] for h in history]

    fig = go.Figure()

    # Add the focus score line
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

    # Add threshold lines
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
        # Sampling control
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
            st.rerun()

    # Sampling status indicator
    if st.session_state.sampling_active:
        st.success("Sampling ACTIVE - Capturing every 10 seconds")
    else:
        st.warning("Sampling PAUSED - Click 'Start Sampling' to begin monitoring")

    st.divider()

    # Main content area
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.subheader("Latest Webcam Capture")

        if st.session_state.latest_image_b64:
            try:
                img = Image.open(
                    BytesIO(base64.b64decode(st.session_state.latest_image_b64))
                )
                st.image(img, use_container_width=True)

                # Display timestamp below image
                if st.session_state.latest_timestamp:
                    st.caption(
                        f"Captured at: {st.session_state.latest_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            except Exception as e:
                st.warning(f"Cannot display image: {e}")
        else:
            st.info("Waiting for first capture... Start sampling to begin.")

        # Focus Analysis section
        st.subheader("Focus Analysis")
        analysis = shared_state.get("latest_analysis", {})
        if analysis:
            st.write(f"**Observations:** {analysis.get('observations', 'None')}")
        else:
            st.info("No analysis yet...")

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
                index=personas.index(st.session_state.persona)
                if st.session_state.persona in personas
                else 0,
            )

            if selected_persona != st.session_state.persona:
                st.session_state.persona = selected_persona
                update_shared_state({"persona": selected_persona})
                st.success(f"Switched to {selected_persona}")

            # Test audio button
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

        # Audio Player - plays pending audio with autoplay
        if st.session_state.pending_audio:
            st.subheader("Audio Response")
            st.audio(st.session_state.pending_audio, format="audio/wav", autoplay=True)
            # Clear after displaying (will play once)
            st.session_state.pending_audio = None

    st.divider()

    # Focus History Chart
    st.subheader("Focus History")
    render_focus_chart()

    # Auto-refresh when sampling is active
    if st.session_state.sampling_active:
        # Capture and analyze
        with st.spinner("Capturing..."):
            capture_and_analyze()

        # Schedule next capture in 10 seconds
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
