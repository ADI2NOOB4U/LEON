<div align="center">

# LEON

### A local-first AI workspace for thinking, building, and getting things done.

<p>
  <a href="https://github.com/ADI2NOOB4U/LEON/actions"><img src="https://img.shields.io/github/actions/workflow/status/ADI2NOOB4U/LEON/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/React-TypeScript-61DAFB?style=flat-square&logo=react&logoColor=111827" alt="React and TypeScript">
  <img src="https://img.shields.io/badge/Privacy-local--first-8B5CF6?style=flat-square" alt="Local first">
</p>

<p><strong>Memory</strong> · <strong>Vision</strong> · <strong>Voice</strong> · <strong>Tasks</strong> · <strong>Tools</strong> · <strong>Orchestration</strong></p>

</div>

LEON is a personal AI operating layer built around one principle: use the smallest, safest capability that can complete the request. Deterministic requests go directly to local tools; model calls happen when they add real value; private data stays local by default.

## Why LEON

Most assistants turn every message into a large-model conversation. LEON takes a different path:

```text
message → Intelligence Core → intent → capability → permission
        → executor → verification → clear, honest response
```

That makes the system faster, easier to extend, more private, and much less likely to claim an action happened when it did not.

## What is inside

| Layer | What it does |
| --- | --- |
| **Intelligence Core** | Deterministic-first routing, route scoring, provider selection, privacy classification, fallbacks, and telemetry. |
| **Local models** | Ollama roles for general chat, coding, vision, and embeddings. |
| **Action boundary** | `ActionAuthority` enforces SAFE / CONFIRM / BLOCKED permissions before tools run. |
| **Workspace** | Persistent memory, background tasks, planner/worker execution, schedules, notifications, and research. |
| **Perception** | Snapshot-based local vision, OCR, screen analysis, speech-to-text, and text-to-speech. |
| **Integrations** | Spotify/media, browser, filesystem, Git, desktop applications, email, and optional Gemini research. |

## Intelligence Core

The core is exposed for safe route inspection during development:

```http
POST /api/intelligence/route
Content-Type: application/json

{"message":"what time is it?"}
```

Example response:

```json
{
  "intent": "datetime.current",
  "confidence": 0.91,
  "route": "system.datetime",
  "provider": "local",
  "needs_web": false,
  "needs_vision": false,
  "needs_memory": false,
  "requires_confirmation": false
}
```

The diagnostic endpoint never executes an action. Real execution continues through the existing permission and verification boundaries.

## Supported routes

| Request | Route |
| --- | --- |
| `hello` | Local general conversation |
| `what time is it?` | Operating-system clock |
| `what is my CPU usage?` | Local system statistics |
| `write a Python function...` | Local coding model |
| `what's on my screen?` | Screen capture + local vision |
| `remember that...` | Persistent memory |
| `play ... on Spotify` | Spotify playback + playback verification |
| `play ... on YouTube Music` | Opens a YouTube Music search in the default browser |
| `open VS Code` | Desktop tool + confirmation |
| `latest AI news` | Current-information research route |
| `create a project, run tests, fix failures` | Planner and background task system |

## Quick start

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Spotify

Spotify playback needs a Spotify Developer app. Add its client ID and client secret to the backend environment as `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`, then register the exact URL in `SPOTIFY_REDIRECT_URI` (by default, `http://127.0.0.1:8000/api/media/spotify/callback`) in that app's redirect URI settings. Restart the backend after changing the environment. The client secret and OAuth tokens must remain backend-only.

Once configured, authorize Spotify from the Media panel, then use typed or voice commands such as `play I Can't Let You Go by K3NT4 on Spotify`, `pause Spotify`, or `what's playing on Spotify?`. Explicit voice requests run without a second confirmation; typed playback changes still ask for confirmation. Playback is confirmed against Spotify's current device state; LEON reports a failure when no device, Premium permission, or track is available.

YouTube Music voice commands such as `play Here Comes the Sun by The Beatles on YouTube Music` open a search in the default browser. Select a result there to begin playback; browser autoplay is not bypassed. Pause/next/previous voice controls are available when Windows media controls are enabled (`WINDOWS_MEDIA_ENABLED=true`) and YouTube Music has an active browser media session.

### Gmail

LEON can send plain-text Gmail messages through the Gmail API. Enable the Gmail API in Google Cloud, create an OAuth client, obtain a refresh token with Gmail send permission, and set `EMAIL_PROVIDER=gmail`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, and `GMAIL_SENDER` in `backend/.env`. Never put these values in the frontend or commit them. Install dependencies with `python -m pip install -r backend/requirements.txt` and restart the backend.

Use the command bar or voice with the explicit form `send an email to person@example.com subject Meeting body The meeting is at 10 AM.` LEON previews the recipient and subject and requires confirmation before sending. Readiness is available at `/api/email/status`; account creation and password-based Gmail automation are intentionally unsupported.

### Optional local models

```text
qwen3:8b                 general chat
qwen2.5-coder:7b        coding
qwen3-vl:8b             vision
qwen3-embedding:0.6b   local memory embeddings
```

Configure the backend through [`backend/.env.example`](backend/.env.example). Keep API keys, OAuth tokens, and secrets in the backend environment only.

## Voice and vision

Voice follows the same core as typed requests:

```text
microphone → STT → Intelligence Core → executor → response → TTS
```

Vision is snapshot-first and local-only by default. Frames are not persisted, added to memory, or sent to web search. See the environment example for model paths and size limits.

## Development

Run the full validation suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm run typecheck
npm run build
```

Current workspace validation: **262 backend tests passing**, frontend typecheck passing, and frontend production build passing.

## Controlled self-improvement

LEON can learn response-quality preferences from explicit user feedback. The learning cycle requires repeated low-rated outcomes, creates a versioned proposal, applies a safety gate, and supports rollback. It only updates response guidance; it cannot change permissions, tools, action authority, or security policy.

The API is available under `/api/improvement`:

- `POST /feedback` records a 1–5 rating and verified outcome.
- `POST /learn` evaluates repeated negative evidence and activates safe guidance.
- `GET /profile` and `GET /proposals` expose the current learning state.
- `POST /proposals/{id}/rollback` reverts an active proposal.

## Project map

```text
backend/app/
├── intelligence/   routing brain, schemas, registry, metrics, verification
├── core/           agent, providers, planner, authority, research
├── tools/          safe executors and capability integrations
├── memory/         persistent local memory
├── jobs/           worker and scheduler
├── voice/          STT/TTS pipeline
└── vision/         image and screen analysis

frontend/src/
├── components/     workspace panels and the LEON core visual
├── api/             typed backend client
├── interactions/   sound and cursor interaction layer
└── styles.css      visual system and responsive layout
```

## Design commitments

- **Local first:** private workspace data and local files stay local by default.
- **Deterministic first:** clocks, system stats, media controls, and obvious tools do not need an LLM.
- **Permission aware:** confidence never silently grants action authority.
- **Verified execution:** a successful command response is not treated as proof until the result is checked.
- **Honest fallbacks:** unavailable providers produce explicit failures, never fabricated success.
- **Small, composable architecture:** specialized executors remain useful while the Intelligence Core provides one routing brain.

## Status

LEON is an actively developed local AI workspace. The core platform, API surface, frontend shell, memory, vision, voice, task system, and deterministic orchestration are implemented. Optional capabilities such as Spotify, Gemini research, Ollama models, and native media discovery depend on local configuration and provider availability.

## Government and business readiness

For a department-facing product brief, pilot plan, procurement model, and production acceptance criteria, see [`docs/GOVERNMENT_BUSINESS_PROPOSAL.md`](docs/GOVERNMENT_BUSINESS_PROPOSAL.md). A shorter product overview is available in [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md).

For the complete reviewer path, start at [`docs/README.md`](docs/README.md). It links the architecture, security posture, deployment model, commercial packaging, and production-readiness checklist.

## License

No license has been declared yet. Until one is added, all rights are reserved.
