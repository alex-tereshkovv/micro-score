# Senim Risk Workstream Chats

Last updated: 2026-07-17

This document defines how separate Codex chats should cooperate on Senim Risk.
Each chat owns a workstream, but the repo keeps one shared product direction.

## Standard Startup

Every workstream chat should begin by reading:

- `docs/CURRENT_STATUS.md`
- `docs/PRODUCT_ROADMAP.md`
- `docs/WORKSTREAMS.md`

Then read the relevant local files for the requested work:

- backend/API work: `docs/API_CONTRACT.md`, `src/microscore_api/`,
  `tests/test_api_*.py`
- frontend work: `apps/web/`, `scripts/*smoke.js`, `tests/test_web_static.py`
- fullstack workflow work: backend, frontend, contract docs, and smoke tests
- QA/release work: `scripts/check.ps1`, `docs/RELEASE_CHECKLIST.md`, tests, and
  smoke scripts
- analytics/ML work: `src/microscore/`, `data/`, `reports/`, research docs, and
  modeling tests

## Workstreams

### Coordination and Roadmap

Owns cross-chat priorities, roadmap/status docs, release sequencing, and
conflict resolution. This chat should decide what becomes `Now`, `Next`, or
`Later`, then hand implementation to the relevant workstream.

### Backend, API, and Security

Owns `src/microscore_api/`, API schemas, persistence, auth/session behavior,
tenant isolation, admin controls, invite/session/MFA readiness, and API tests.

Contract rule: any response/request shape change must update
`docs/API_CONTRACT.md`, frontend/static demo behavior, and tests.

### Frontend and Web Prototype

Owns `apps/web/`, static demo behavior, browser-facing UX states, frontend smoke
scripts, and static frontend tests.

Contract rule: the frontend should consume the API contract and existing mock
API behavior instead of inventing backend-only fields.

### Fullstack Product Flows

Owns user journeys that cross surfaces, especially borrower application
submission/history/status and MFI scoring/review/decision workflows.

Contract rule: update backend, web/static demo, docs, and release coverage in
one increment when the flow changes.

### QA and Release Gate

Owns `scripts/check.ps1`, test coverage, static smoke coverage, release
checklist accuracy, and regression triage.

Contract rule: release-gate changes should prove current behavior, not silently
weaken product or security expectations.

### Analytics, ML, and Research

Owns `src/microscore/`, modeling scripts, datasets, research artifacts,
calibration/proxy audits, and model documentation.

Contract rule: analytics and model outputs used by the product must be clearly
labeled as synthetic/prototype unless validated on real permitted data.

## Multi-Chat Contract Rules

- API contract changes require backend code, schema/docs, frontend/static demo,
  and tests to move together.
- Behavioral signal changes require typed backend validation, frontend
  validation, mock API parity, and smoke coverage.
- Tenant changes require queue, analytics, export, review, and admin behavior to
  stay organization-scoped.
- Security/admin changes must not expose raw passwords, raw invite tokens, raw
  bearer tokens, or borrower-private data through list/audit surfaces.
- Borrower lifecycle changes must keep terminal-state guards and borrower-safe
  projections intact.
- ML/research claims must keep synthetic-data and proxy-feature limitations
  visible.

## Standard Handoff

Each chat should finish a meaningful increment with:

- changed files and why they changed;
- tests or smoke checks run;
- checks not run and why;
- any required update to `docs/CURRENT_STATUS.md`;
- any cross-workstream follow-up that should become a task in another chat.

## Suggested Initial Prompts

Use these prompts when opening a workstream chat:

```text
You are the Senim Risk Backend/API/Security workstream. Start by reading docs/CURRENT_STATUS.md, docs/PRODUCT_ROADMAP.md, docs/WORKSTREAMS.md, and docs/API_CONTRACT.md. Own backend/API/security work only, and keep API contract changes synchronized with frontend/static demo/tests.
```

```text
You are the Senim Risk Frontend/Web workstream. Start by reading docs/CURRENT_STATUS.md, docs/PRODUCT_ROADMAP.md, docs/WORKSTREAMS.md, apps/web/, and the relevant smoke scripts. Improve browser UX while respecting the existing API contract.
```

```text
You are the Senim Risk Fullstack Product Flows workstream. Start by reading docs/CURRENT_STATUS.md, docs/PRODUCT_ROADMAP.md, docs/WORKSTREAMS.md, docs/API_CONTRACT.md, apps/web/, and relevant tests. Own end-to-end borrower and MFI review flows across backend, frontend, docs, and smoke coverage.
```

```text
You are the Senim Risk QA/Release Gate workstream. Start by reading docs/CURRENT_STATUS.md, docs/WORKSTREAMS.md, docs/RELEASE_CHECKLIST.md, scripts/check.ps1, and the smoke/test files. Keep the release gate accurate and useful.
```

```text
You are the Senim Risk Analytics/ML/Research workstream. Start by reading docs/CURRENT_STATUS.md, docs/PRODUCT_ROADMAP.md, docs/WORKSTREAMS.md, src/microscore/, data/, reports/, and modeling tests. Keep research artifacts reproducible and claims clearly limited.
```
