# Senim Risk Current Status

Last updated: 2026-07-17

Use this file as the short handoff for every Senim Risk workstream chat. Read it
with `docs/PRODUCT_ROADMAP.md`, `docs/WORKSTREAMS.md`, and the relevant contract
or release documents before changing behavior.

## Sources of Truth

- `docs/PRODUCT_ROADMAP.md` is the long-range product roadmap.
- `docs/CURRENT_STATUS.md` is the current cross-chat coordination snapshot.
- `docs/WORKSTREAMS.md` defines chat boundaries, startup rules, and handoff
  expectations.
- `docs/API_CONTRACT.md` is the backend/frontend contract reference.
- `docs/RELEASE_CHECKLIST.md` is the release gate reference.

When implementation changes the product contract, update the API, web/static
demo, tests, smoke scripts, and docs together.

## Current Product State

Senim Risk is a local portfolio-ready prototype with:

- a packaged research/ML layer under `src/microscore`;
- a FastAPI backend under `src/microscore_api`;
- SQLite development persistence for users, sessions, organizations,
  applications, scores, model versions, staff invites, simulations, and audit
  events;
- borrower, MFI analyst, and admin role flows;
- tenant-scoped MFI queues, analytics, CSV export, review packets, lifecycle
  decisions, and simulation history;
- staff invite, staff lifecycle, session control, prototype MFA, and security
  readiness controls;
- a static web prototype under `apps/web`;
- release validation through Python tests and Node smoke scripts.

The stable local release gate remains:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

Manual browser smoke can be useful, but the durable proof on this Windows setup
is the automated API, static frontend, and smoke coverage.

## Now

The active engineering direction is to make the frontend and scoring review
flow feel more production-like while preserving the existing security and
privacy boundary.

Priority product slice:

- borrower submits a consented application;
- MFI analyst scores it, opens the review packet, records a decision, and sees
  decision/history context;
- borrower sees an owned, borrower-safe status update;
- admin can inspect readiness/audit state without exposing raw secrets;
- the release gate proves the flow across API, static demo, and tests.

## Next

- Frontend: improve production-like UX states for the borrower/MFI/admin
  workflows without inventing new backend contracts.
- Backend: continue closing pre-pilot gaps around PostgreSQL migration,
  production identity/MFA, transactional invite delivery, and contract clarity.
- Fullstack: keep borrower lifecycle and MFI review flows synchronized across
  API, web, static demo, and tests.
- QA: keep `scripts/check.ps1`, frontend smoke tests, and release checklist
  aligned with the current product flow.
- Analytics/ML: continue KZT calibration planning, proxy-feature monitoring,
  model documentation, and reproducible research artifacts.

## Coordination Risks

- Synthetic model results must not be described as real lending validation.
- Real borrower data is out of scope until privacy, consent, identity,
  deployment, and security controls are production-ready.
- `organization_id` and tenant scoping are contract-critical; queue, analytics,
  export, scoring, and review behavior must remain organization-scoped.
- Borrower-facing responses must stay borrower-safe and must not expose internal
  score snapshots, analyst notes, staff identity, raw secrets, or policy
  metadata.
- Changes to behavioral signals, lifecycle statuses, auth/session shapes, staff
  invite shapes, or analytics schemas are multi-surface changes.

## Handoff Rule

At the end of a meaningful workstream increment, update this file only when the
actual current status, active priority, or coordination risk has changed. Keep
the update short so future chats can load the project state quickly.
