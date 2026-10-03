# Architecture

## Current state

### DONE
- FastAPI application bootstrap with routers for health, chat, command, memory, tasks, and tools.
- SQLite-backed persistence in data/leon.db with migration-safe table creation.
- Core service boundaries: model router, agent/interpreter, task manager, planner, tool registry, memory service.
- Permission level gating for tool execution.
- Background worker loop for queued task execution and cancellation.

### PARTIAL
- Model provider flow is abstracted and includes a mock fallback path so the app continues to function when Ollama or Colibri is unavailable.
- Frontend uses a central API client but is still a clean UI shell instead of a full product app.

### NOT STARTED
- Real browser automation, desktop integration, voice processing, and cross-device synchronization.
- Advanced planner/executor orchestration beyond the current queued task engine.

### BLOCKED
- Real LLM execution is blocked until a provider runtime is available and configured.

## Structure

- backend/app/api: HTTP entrypoints
- backend/app/core: router, planner, agent, interpreter
- backend/app/jobs: task lifecycle and worker
- backend/app/memory: SQLite-backed memory service
- backend/app/tools: registry and safe system tools
- backend/app/security: permission enforcement
- frontend/src: React/Vite UI shell and 3D visual layer

## Architectural intent

The project remains intentionally modular and local-first. Current work stabilizes the foundation before adding future autonomous features.
