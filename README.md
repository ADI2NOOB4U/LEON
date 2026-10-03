# LEON

LEON is a local-first personal AI system with a modular backend, persistent memory, task orchestration, and a premium desktop-style frontend foundation.

## Current status

### DONE
- FastAPI backend foundation is in place and serving core API routes.
- SQLite persistence for tasks and memory is working.
- Background task lifecycle and retry/cancel flow are implemented.
- Tool registry and permission checks are in place for safe system tools.
- Planner and memory APIs are functional.
- Backend test suite is passing in the current repo state.
- Frontend shell, motion styling, and 3D core visual foundation are implemented.
- Frontend build and typecheck pass in this workspace.

### PARTIAL
- Model provider abstraction exists and now gracefully falls back to the built-in mock provider when a configured runtime is unavailable.
- Frontend is connected to real backend endpoints for health and task creation, but not yet to all advanced features or memory/tool UIs.
- The task system is operational as a background job loop, but it is still modular and deterministic rather than autonomous AI execution.
- Visual frontend direction is defined, but the product remains a foundational shell rather than the final full product experience.

### NEWS & PERSONAL BRIEFINGS
- News subscriptions support the built-in cybersecurity, AI, technology, and India topics plus validated custom topics.
- Collection uses LEON's read-only Playwright search tool and allowlisted configured sources; URLs are validated, deduplicated, and stored with retrieval metadata.
- Stories receive explainable critical, important, interesting, or ignore classifications and are compared against bounded, topic-relevant LEON memory.
- Briefings preserve facts, source URLs, and LEON interpretation separately, with persisted history and included source records.
- Morning, evening, and timezone-qualified custom schedules are durable SQLite jobs. Interrupted jobs recover on restart and duplicate active jobs are not created.
- Desktop/push notification interface and configured email delivery are supported. Delivery failures are recorded without losing the briefing.
- Configure provider behavior through the existing `notification_provider`, `email_provider`, and email recipient settings. News does not post to external services.

### NOT STARTED
- Browser automation, desktop control, voice, vision, email, phone integration, and cross-device sync.
- Full autonomous planning/execution beyond current modular task flow.
- Vector or semantic memory.
- Remote push provider implementations beyond the existing provider interface.
- RSS/API source adapters and richer published-time extraction (the current collector intentionally stays within the existing browser/search infrastructure).
- Production-grade provider orchestration beyond the current mock/Ollama abstraction.

### BLOCKED
- Real Ollama-backed chat flow is blocked because Ollama is not installed in this environment.
- Full AI/autonomous execution beyond the current task engine remains intentionally out of scope for the current milestone.

## Run locally

Backend:
- python -m pip install -r backend/requirements.txt
- python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

Frontend:
- cd frontend
- npm install
- npm run dev

## Local voice

Voice conversations run locally. Install `backend/requirements.txt`, then place a
CTranslate2 faster-whisper model directory at `data/models/faster-whisper-small`
and a Piper voice plus its matching `.onnx.json` file at
`data/models/piper/en_US-lessac-medium.onnx`. Model files are not downloaded by
the server; both paths can be overridden with `VOICE_STT_MODEL_PATH` and
`VOICE_TTS_MODEL_PATH`. The default faster-whisper configuration uses CPU int8
and loads models lazily, so missing models produce an actionable API error.

Open the frontend on localhost and allow microphone access. Select **Start
listening**, speak, then select **Stop listening** to send the recording to
LEON. Voice uses the existing chat agent and does not include wake-word
detection. Piper remains the local default; Fish Audio is optional.

To use Fish Audio for speech output, set `VOICE_PROVIDER=fish_audio` and
`FISH_AUDIO_API_KEY` in the backend environment. Optionally set
`FISH_AUDIO_REFERENCE_ID` to a Fish Audio voice model ID and
`FISH_AUDIO_MODEL` to select a model (defaults to `s2.1-pro-free`). The key
stays on the backend. Fish Audio failures fall back to the configured local
Piper voice; if both providers fail, the transcript and text reply are still
returned.

## Validation

Current verified status in this workspace:
- Backend tests: 100 passed
- Frontend typecheck/build: passed (`leon-ui/npm run build`)
- `git diff --check`: passed (Git reports only existing line-ending normalization notices)

## Notes

This repository is intentionally stabilized around the current milestone rather than claiming future AI features are complete. The goal is a maintainable foundation for the next implementation phase.
