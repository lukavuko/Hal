# Interface Service

Streamlit-based UI for the Hal focus accountability system.

## Overview

The interface provides user controls for monitoring, calibration, and configuration. It communicates with the backend via REST APIs and displays real-time focus status.

**Port**: 8000 (Streamlit) + 5050 (internal API)

## Architecture

```
┌─────────────────────────────────────────┐
│           Interface Container           │
│  ┌─────────────────┐  ┌──────────────┐ │
│  │   Streamlit     │  │  Flask API   │ │
│  │   (port 8000)   │◄─┤  (port 5050) │ │
│  └────────┬────────┘  └──────────────┘ │
└───────────┼─────────────────────────────┘
            │
            ▼
      Backend (:5000)
```

## Features

- **Calibration Wizard** - Capture baseline "focused" image on first run
- **Start/Stop Sampling** - User-controlled monitoring activation
- **Live Status Display** - GREEN/YELLOW/RED state with numeric focus score
- **Webcam Preview** - Latest capture with timestamp
- **Focus History Chart** - Line chart of focus scores over time
- **Persona Selection** - Choose voice character (Hal, Sarcastic Friend, etc.)
- **Event Log** - Recent state changes and agent responses

## Requirements

- Must ask user for permission before enabling webcam sampling
- Must display timestamp below captured photos
- Must show focus level indicator (RED/YELLOW/GREEN) with numeric score (0-100)
- Must access backend endpoints at `/vision`, `/mind`, and `/speech`
- Must display focus history as a line chart
- Must allow voice character selection

## File Structure

```
interface/
├── Dockerfile
├── requirements.txt
└── src/
    ├── app.py           # Main Streamlit application
    ├── api_server.py    # Internal Flask API for state management
    └── .streamlit/
        └── secrets.toml # Backend URL configuration
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | 5050 | Internal Flask API port |
| `BACKEND_URL` | http://backend:5000 | Backend service URL |

## Dependencies

```
streamlit>=1.29.0
flask>=3.0.0
requests>=2.31.0
pillow>=10.1.0
plotly>=5.18.0
```

## Running Locally

```bash
cd services/interface
docker build -t hal-interface .
docker run -p 8000:8000 -p 5050:5050 hal-interface
```

Access at: http://localhost:8000
