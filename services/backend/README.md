# Backend Service

Single Flask application hosting vision, mind, and speech modules for the Hal focus accountability system.

## Overview

The backend provides all AI-powered functionality: webcam capture, focus analysis via Ollama multimodal LLM, response generation, and text-to-speech via Piper TTS.

**Port**: 5000

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Backend Container (port 5000)                  │
│  ┌────────────────────────────────────────────────────────┐│
│  │                  Flask App (app.py)                    ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  ││
│  │  │   /vision   │ │   /mind     │ │    /speech      │  ││
│  │  │  Blueprint  │ │  Blueprint  │ │    Blueprint    │  ││
│  │  └─────────────┘ └─────────────┘ └─────────────────┘  ││
│  └────────────────────────────────────────────────────────┘│
│                            │                               │
│            ┌───────────────┼───────────────┐               │
│            ▼               ▼               ▼               │
│      webcam.py       personas/*.txt   text2speech.py       │
│      analysis.py      evaluator.py     (Piper TTS)         │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Ollama Server  │
                    │  (external)     │
                    └─────────────────┘
```

## Endpoints

### Root
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Aggregated health check |
| `/` | GET | API info and endpoint list |

### Vision (`/vision`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/vision/capture` | POST | Capture webcam photo, return JPEG bytes |
| `/vision/calibrate` | POST | Store calibration image (multipart file) |
| `/vision/analyze` | POST | Analyze image with Ollama, return focus_score (0-100) |

### Mind (`/mind`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mind/evaluate` | POST | Evaluate analysis, generate persona response if RED |
| `/mind/state` | GET | Get current focus state (GREEN/YELLOW/RED) |

### Speech (`/speech`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/speech/speak` | POST | Convert text to speech, return WAV audio bytes |
| `/speech/voices` | GET | List available voices |

## File Structure

```
backend/
├── Dockerfile
├── requirements.txt
├── WINDOWS_WEBCAM_SETUP.md
└── src/
    ├── app.py              # Main Flask app with blueprints
    ├── config.py           # Config loader for models.yml
    ├── models.yml          # Model and persona configuration
    ├── vision/
    │   ├── __init__.py     # Blueprint registration
    │   ├── routes.py       # Endpoint handlers
    │   ├── webcam.py       # OpenCV webcam capture
    │   └── analysis.py     # Ollama vision analysis
    ├── mind/
    │   ├── __init__.py     # Blueprint registration
    │   ├── routes.py       # Endpoint handlers
    │   └── evaluator.py    # Focus state logic + LLM response
    ├── speech/
    │   ├── __init__.py     # Blueprint registration
    │   ├── routes.py       # Endpoint handlers
    │   └── text2speech.py  # Piper TTS wrapper
    └── personas/
        ├── Hal.txt
        ├── SarcasticFriend.txt
        ├── MotivationalCoach.txt
        └── DrillSergeant.txt
```

## Configuration (models.yml)

```yaml
ollama:
  url: "http://host.docker.internal:11434"
  vision_model: "llava:7b"        # Multimodal for image analysis
  text_model: "llama3.2:3b"       # Text generation for responses

focus:
  green_threshold: 50             # Score >= 50 = GREEN
  yellow_threshold: 25            # Score >= 25 = YELLOW, else RED

voices:
  hal:
    persona_file: "personas/Hal.txt"
    # ... TTS model URLs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | Flask server port |
| `OLLAMA_URL` | http://host.docker.internal:11434 | Ollama API URL |
| `PIPER_CACHE` | /app/models | TTS model cache directory |
| `CONFIG_PATH` | src/models.yml | Configuration file path |

## Dependencies

```
flask>=3.0.0
pyyaml>=6.0.1
requests>=2.31.0
opencv-python-headless>=4.8.0
pillow>=10.1.0
numpy>=1.26.0
piper-tts>=1.2.0
onnxruntime>=1.16.0
```

## External Dependencies

- **Ollama**: Must be running with `llava:7b` and `llama3.2:3b` models pulled
- **Webcam**: `/dev/video0` device passthrough required

## Running Locally

```bash
# Start Ollama first
ollama serve

# Pull required models
ollama pull llava:7b
ollama pull llama3.2:3b

# Build and run backend
cd services/backend
docker build -t hal-backend .
docker run -p 5000:5000 --device=/dev/video0 hal-backend
```

## Windows Webcam Setup

See [WINDOWS_WEBCAM_SETUP.md](WINDOWS_WEBCAM_SETUP.md) for WSL2 webcam passthrough instructions.
