# Contributing to LEON

LEON is developed as a privacy-aware, permissioned AI platform. Contributions should preserve those boundaries.

## Before opening a pull request

- run `.\.venv\Scripts\python.exe -m pytest backend/tests -q`;
- run `npm run typecheck` and `npm run build` from `frontend`;
- run `git diff --check`;
- add tests for behavior changes;
- document new configuration, permissions, data flows, and failure states;
- remove secrets, tokens, personal data, and private workspace contents from logs and fixtures.

## Review expectations

Changes involving tools, browser/desktop control, external providers, memory, cloud routing, authentication, or records must include a security and privacy review in the pull request description.

Do not weaken `ActionAuthority`, secret redaction, provider availability checks, confirmation requirements, or verification behavior for convenience.
