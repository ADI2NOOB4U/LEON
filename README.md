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

### NOT STARTED
- Browser automation, desktop control, voice, vision, email, phone integration, and cross-device sync.
- Full autonomous planning/execution beyond current modular task flow.
- Vector or semantic memory.
- Advanced scheduling and notification systems.
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

## Validation

Current verified status in this workspace:
- Backend tests: 24 passed
- Frontend typecheck: passed
- Frontend build: passed

## Notes

This repository is intentionally stabilized around the current milestone rather than claiming future AI features are complete. The goal is a maintainable foundation for the next implementation phase.
