# LEON roadmap

The roadmap separates product capability from deployment assurance. A feature can be technically implemented while still requiring department-specific approval before production use.

## Delivered foundation

- FastAPI backend and React/Vite workspace.
- SQLite persistence for tasks, memory, missions, events, and operational state.
- Deterministic-first Intelligence Core with typed route decisions.
- SAFE / CONFIRM / BLOCKED action authority.
- Tool registry, planner, worker, scheduler, missions, and verification paths.
- Local-first model routing for general chat, coding, vision, embeddings, and current-information research.
- Voice, vision, memory, computer-use, observability, evaluation, and controlled improvement foundations.
- Automated backend regression suite and frontend typecheck/build validation.

## Next product priorities

1. Finish end-to-end frontend coverage for missions, evaluation, observability, memory, and administration.
2. Add department-configurable workflow templates and approved integration adapters.
3. Improve multilingual, accessibility, and document-processing support.
4. Expand evaluation datasets with department-approved, anonymized cases.
5. Harden provider health, degraded mode, and operator diagnostics.

## Deployment-assurance priorities

1. Add identity-provider integration and role-based authorization.
2. Add tamper-evident audit storage and administrator access controls.
3. Formalize retention, deletion, export, legal-hold, and records-management behavior.
4. Complete threat modeling, dependency scanning, penetration testing, and remediation tracking.
5. Test backup restoration, disaster recovery, capacity, and availability objectives.
6. Complete accessibility and language validation with representative users.

## Release gates

### Pilot release

Requires a scoped deployment, approved workflows, sanitized or low-sensitivity data, trained users, evaluation baseline, incident owner, and documented limitations.

### Production release

Requires the controls in [Production readiness](PRODUCTION_READINESS.md), department acceptance evidence, security/privacy approval, operational runbooks, tested recovery, and a signed support/exit plan.
