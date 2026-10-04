# Security

## Current state

### DONE
- Secrets are not committed to the repository, and environment files are ignored by git.
- Tool execution is permission-gated using explicit SAFE/CONFIRM/BLOCKED rules.
- System tools are intentionally narrow and do not allow unrestricted shell access.
- Open app execution validates Windows application names and blocks path traversal or shell injection patterns.
- CORS is limited to local frontend origins.
- `GEMINI_API_KEY` is backend-only and stored as a secret setting; it is not
  part of frontend configuration or API response schemas.
- Gemini requests include only the latest direct user text, omit memory and
  prior turns, and set `store=false`. Requests containing private/sensitive
  markers, credentials, local files, images, or recordings are blocked from
  automatic cloud routing.
- Automatic Ollama-to-Gemini fallback is limited to safe public general chat
  after a local provider failure. Coding and vision requests never use this
  fallback. Vision remains on local Ollama.
- Current/latest requests use the Gemini Interactions API `google_search` tool
  when Search grounding is enabled; without it, live requests fail closed.
- Web/research content is data only. Tool execution still goes through the
  registered ToolRegistry and SAFE/CONFIRM/BLOCKED permission checks.
- Mission execution does not create a second authorization path: every mission
  tool call still goes through ActionAuthority, and confirmation-gated steps
  pause the mission until user approval is recorded.
- Mission completion requires step execution plus deterministic verification;
  failed verification enters the bounded retry/repair path and cannot be
  reported as completed.

### PARTIAL
- The application remains local-first and does not yet implement a full user-auth model.
- More advanced runtime policy checks and audit logging are still future work.

### NOT STARTED
- User authentication and authorization across remote access.
- Full audit logs for every tool and model action.
- Full threat model review for future browser/desktop automation features.

### BLOCKED
- No major blocker currently exists for the current local-first milestone.

## Security principles

- Prefer explicit permissions over broad execution.
- Keep local-first execution and avoid exposing secrets to the frontend.
- Require confirmation for sensitive actions.
- Do not add destructive automation without a clear approval boundary.
