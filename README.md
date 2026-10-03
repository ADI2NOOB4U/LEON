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
- Model routing supports role-specific local Ollama models and optional Gemini. Provider failures are surfaced; only safe public general chat may automatically fall back to Gemini when cloud AI is enabled.
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
- Browser automation, desktop control, email, phone integration, and cross-device sync.
- Full autonomous planning/execution beyond current modular task flow.
- Vector or semantic memory.
- Remote push provider implementations beyond the existing provider interface.
- RSS/API source adapters and richer published-time extraction (the current collector intentionally stays within the existing browser/search infrastructure).
- Cross-provider fallback beyond the explicitly limited safe public chat case.

### BLOCKED
- Ollama-backed requests require a running Ollama service and the configured local model.
- Gemini live research and cloud fallback require explicit cloud opt-in and a backend-only Gemini API key.
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
`VOICE_TTS_MODEL_PATH`. If the standard Piper path is absent, the matching
default voice and config at the repository root are also recognized. The
default faster-whisper configuration uses CPU int8 and loads models lazily, so
missing models produce an actionable API error.

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

## Gemini cloud routing

Gemini is an optional backend provider. Copy the settings from
`backend/.env.example` into `backend/.env`, set `CLOUD_AI_ENABLED=true`, and
provide `GEMINI_API_KEY` there. The API key must remain in the backend
environment; do not add it to frontend environment variables or return it in
API responses. Google Search grounding is controlled by
`CLOUD_AI_SEARCH_GROUNDING` and defaults to enabled.

Normal, coding, and image requests prefer local Ollama models
(`qwen3:8b`, `qwen2.5-coder:7b`, and `qwen3-vl:8b`). Requests asking for current,
latest, or today's information route to Gemini live research and require Search
grounding. A direct request to use Gemini selects Gemini. If Ollama fails,
only a safe public general-chat request may be retried with Gemini, and only
when cloud AI is enabled. Sensitive/private prompts are never automatically
uploaded. Cloud requests contain only the latest direct user text; they omit
memory, prior conversation turns, system context, local files, images, and
recordings. Gemini Interactions are sent with `store=false`.

Gemini calls use Google's Interactions API and its `google_search` tool
(`https://ai.google.dev/gemini-api/docs/interactions` and
`https://ai.google.dev/gemini-api/docs/google-search`). Disabling Search
grounding makes current/latest requests fail explicitly rather than returning
an ungrounded answer as if it were live research. Provider failures are
reported rather than silently replaced with mock output.

## Validation

Current verified status in this workspace:
- Backend tests: 201 passed, including voice and vision tests.
- Frontend typecheck/build: passed (`frontend/npm run typecheck` and `frontend/npm run build`).
- Real local Ollama chat smoke: passed.
- Live Gemini/Google Search smoke: unavailable because cloud AI is disabled and no Gemini API key is configured in this environment.
- `git diff --check`: passed (Git reports only existing line-ending normalization notices)

## Notes

This repository is intentionally stabilized around the current milestone rather than claiming future AI features are complete. The goal is a maintainable foundation for the next implementation phase.

## Vision V1

Vision is a snapshot-first, local-only perception path. The frontend requests the camera only after the user activates Vision, captures one frame (or accepts a PNG/JPEG/WebP upload), and sends it to `POST /api/vision/analyze`. The backend validates and decodes the image, then uses the shared Ollama provider with `VISION_MODEL` (default `qwen3-vl:8b`). Frames are not persisted, added to memory, sent to web search, or sent to Fish Audio. Text visible in images is treated as untrusted data and cannot authorize tools or actions.

Configure `VISION_ENABLED`, `VISION_MODEL`, `VISION_MAX_IMAGE_MB`, `VISION_MAX_WIDTH`, `VISION_MAX_HEIGHT`, and `VISION_TIMEOUT_SECONDS` through the existing backend settings. Install the configured model with Ollama before use. V1 supports general, OCR, screen, document, and object modes; it does not continuously monitor a camera or desktop.
