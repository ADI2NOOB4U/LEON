# Security

## Current state

### DONE
- Secrets are not committed to the repository, and environment files are ignored by git.
- Tool execution is permission-gated using explicit SAFE/CONFIRM/BLOCKED rules.
- System tools are intentionally narrow and do not allow unrestricted shell access.
- Open app execution validates Windows application names and blocks path traversal or shell injection patterns.
- CORS is limited to local frontend origins.

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
