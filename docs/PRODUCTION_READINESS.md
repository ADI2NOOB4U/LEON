# Production-readiness dossier

**Purpose:** provide an honest, reviewable path from the current engineering baseline to a department-approved deployment.

LEON is currently a **pilot foundation**, not a pre-certified government system. The gates below define the evidence required before production use.

## Readiness gates

| Gate | Current position | Evidence required before production |
| --- | --- | --- |
| Product scope | Defined local-first assistant and workflow platform | Approved use-case catalogue and prohibited-use register |
| Core reliability | Automated backend and frontend validation exists | Department acceptance tests, uptime target, load results |
| Data protection | Local-first routing, secret redaction, cloud privacy checks | Data-flow review, retention/deletion rules, DPIA/PIA where applicable |
| Identity | Local development boundary | Department identity provider, RBAC, session policy, MFA where required |
| Auditability | Task logs, metrics, and operational events exist | Access-controlled audit store, retention, export, integrity monitoring |
| Authorization | SAFE / CONFIRM / BLOCKED tool boundary | Role-aware policy matrix and approval evidence for every consequential workflow |
| Model governance | Provider roles and evaluation framework exist | Approved model catalogue, version pinning, change review, rollback plan |
| Security | Narrow tools and privacy controls are implemented | Threat model, independent assessment, dependency scanning, remediation record |
| Operations | Background worker and scheduler are present | Runbooks, monitoring, backup/restore test, incident response, support rota |
| Accessibility | Frontend foundation is present | Formal accessibility review against the department's required standard |
| Records | Persistent task and memory data exist | Records classification, legal hold, export, deletion, and archival policy |
| Continuity | Local deployment is possible | Recovery objectives, tested restoration, offline/degraded-mode procedure |

## Recommended pilot evidence pack

1. Architecture and data-flow diagram.
2. Threat model and risk register.
3. Model and integration inventory with versions and owners.
4. Test report covering routing, permissions, privacy, failure handling, and accessibility.
5. Pilot user guide and administrator runbook.
6. Incident response and escalation plan.
7. Backup/restore and disaster-recovery exercise record.
8. User feedback, quality evaluation, and unresolved-issues register.
9. Exit plan covering data export, deletion, and transition to another provider.

## Go/no-go principles

Production approval should be blocked when any of the following is true:

- an official or consequential decision can be made without a named human approver;
- a private data flow to an external provider is not explicitly approved;
- audit records can be silently changed or deleted by ordinary application users;
- backup restoration has not been tested;
- high-severity security findings remain unresolved;
- the department cannot export or delete its data;
- the operating team cannot explain what happens when a provider is unavailable.

## Evidence language

Use “implemented,” “pilot-ready,” and “production-approved” precisely. Do not describe LEON as certified, compliant, autonomous, or risk-free without a completed assessment from the relevant authority.
