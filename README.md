# Hal

A GenAI project for doing GenAi things...

In this case, this project encapsulates a local agent with a sense of humour intended to keep you focused and on task.

It is a locally deployable tool for those needing an accountability agent to help deal with distractions. It may or may not have been inspired by personal experiences... In essence, presented here is a containerized application which will literally monitor you through your webcam (locally of course) while you work. If the accountability agent notices you're off track or not staying focused, it will [comedically] bring it up to remind you that you're slacking. This bot is intended to have a few character types you can choose from, and is entirely designed for comedic purposes.

### Prerequisites:

- Docker
- Webcam
- Speakers
- GPU
- A pressing task that requires prologed periods of focus.

### Project Requirements

- To have a Streamlit UI where the user can check the status of the application, calibrate the agent, and have a record of the applications logging.
- Be able to ingest webcam footage and capture incremental screenshots (every 10 seconds) which will then be sent to the agent.
- Allow the user to take a webcam photo of themselves to calibrate what a focused image looks like in their current context on application startup.
- Have a service which can persist application data locally after application startup. This way, the user only has to calibrate once and that photo will be stored on a mounted local drive somewhere.
- Given a webcam photo, the agent should be able to determine if the individual is focused at their desk with a good level of certainty.
- Be able to identify if the individual is distracted (on their phone, has left the room, not sitting or standing at their desk, etc.)
- If the individual is distracted, switch from a GREEN to YELLOW state and re-evaluate over the next 10 seconds to see if they become focused again.
- If they do not become focused again after 10 seconds (triggered by the initial YELLOW flag), raise a RED flag which will trigger the agent to respond.
- The agent should be able to generate a short response in theme with the agents' prescribed character.
- Have a few characters the user could choose from (it could be a funny sarcastic character or a character inspired from a real source, like Hal from the movie 2001 Space Odyssey)
- Be able to send the short text response to a text-to-audio model for converting the text to voice and then announcing it to the user through their speakers.

### Architectural Requirements

* The entire application will be a docker containerized service intended only to run on local computers.
* The application requires the user has the following: GPU, Webcam, Docker installed, and a set of speakers
* The application will leverage and share the GPU for three separate processes:
  * Image analysis
  * Prompt response generation
  * Text to voice generation
* The application will use microservices that communicate amongst each other to accomplish these tasks.
* The microservices will include:
  * `interface`: Streamlit based user interface that will provide a hub for users to interact with the application. It will be responsible for listening to and receiving POST information from the different microservices where it will either present them or forward them to other services.
  * `backend`:
    * `vision`: A python based worker which will access the webcam and be responsible for capturing the images. It will also be responsible for assessing them for whether the user is focused or not using a local image-to-text model. This model will generate a short report on the users' focus metrics and whether they've deviated from the "calibrated" image or from previous captures. The latest image, text, and metrics produced by this analysis will be exposed to other microservices, specifically the `mind` service.
    * `mind`: A python based worker which will interpret the generated findings (ie. whether user is focused). If it is focused, the current state will be GREEN and will be exposed as such to the interface. If not, this service will update the state to YELLOW and wait for the next available analysis. If again, the state remains 'unfocused', the mind will trigger the second phase process where it uses that text as input to the `persona` module. This module will host the agent's different characters which can be described or inspired from real or fictional archetypes. This persona, while in a RED state, will be prompted by the image analysis result and context to generate a silly text response to the user. The state of the analysis and text response will be forwarded (via POST) to the UI where this information will be displayed. A secondary POST call will be made to the `speech` service which will forward the text and persona details to generate a voice response.
    * `speech`: A python module which will listen to the `mind` and wait until it receives text input to convert to audio (voice). It will use the persona's details and context to select the model to use, and will convert the text to audio using the local GPU. This audio will then be played on the speaker.
* All Models will be sourced from HuggingFace or Ollama. Model configurations are stored in `models.yml` and downloaded on first use. Downloaded models persist in Docker volumes to avoid re-downloading.

### Architectural Decision: Single Backend vs Multi-Service

We evaluated two approaches for the backend architecture:

| Aspect                     | Single Backend (Chosen)                      | Multi-Service (3 Containers)                       |
| -------------------------- | -------------------------------------------- | -------------------------------------------------- |
| **Resource Sharing** | Single process shares GPU/memory efficiently | Each container loads models separately (3x memory) |
| **Complexity**       | One Dockerfile, one container to manage      | 3 Dockerfiles, 3 containers, more orchestration    |
| **Deployment**       | Simple `docker run` or compose             | Requires compose or orchestration                  |
| **Scaling**          | Can't scale services independently           | Can scale speech separately from vision            |
| **Isolation**        | One crash affects all services               | Services isolated, partial failures possible       |
| **Development**      | Must restart entire backend for changes      | Can restart individual services                    |
| **Latency**          | In-process calls, no network overhead        | HTTP calls between services add latency            |

![1767128715681](image/README/1767128715681.png)

**Decision**: Single backend container was chosen because:

- Local machine deployment (no need for independent scaling)
- Shared GPU resources (avoid loading models multiple times)
- Simpler deployment and maintenance
- Lower latency for the interface-driven workflow

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Interface    │────▶│     Backend     │────▶│     Ollama      │
│   (Streamlit)   │     │  (Flask + API)  │     │  (LLM Server)   │
│    :8000        │     │     :5000       │     │    :11434       │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        │   /dev/video0   │
                        │    (Webcam)     │
                        └─────────────────┘
```

**Data Flow:**
1. User clicks "Start Sampling" in Interface
2. Interface requests webcam capture from Backend (`/vision/capture`)
3. Backend captures image, returns to Interface for display
4. Interface sends image to Backend for analysis (`/vision/analyze`)
5. Backend uses Ollama (llava) to analyze focus, returns score 0-100
6. If RED state: Backend generates persona response via Ollama (`/mind/evaluate`)
7. Interface sends text to speech (`/speech/speak`), receives WAV audio
8. Interface plays audio to user

### Quick Start

```bash
# 1. Clone and navigate
git clone <repo>
cd Hal/services

# 2. Start the stack
docker-compose up -d

# 3. Pull Ollama models (first time only, ~6GB total)
docker exec hal-ollama ollama pull llava:7b
docker exec hal-ollama ollama pull llama3.2:3b

# 4. Access the UI
open http://localhost:8000
```

### Project Structure

```
Hal/
├── README.md
├── BEST_PRACTICES.md
└── services/
    ├── docker-compose.yml
    ├── interface/          # Streamlit UI
    │   ├── README.md
    │   ├── Dockerfile
    │   └── src/
    └── backend/            # Vision + Mind + Speech API
        ├── README.md
        ├── Dockerfile
        ├── WINDOWS_WEBCAM_SETUP.md
        └── src/
```

### Resource Requirements

**Minimum:**
- GPU: 6GB VRAM (for Ollama LLM inference)
- RAM: 16GB
- Storage: 10GB (model cache)

**Recommended:**
- GPU: 8GB+ VRAM
- RAM: 32GB
- SSD with 15GB free
