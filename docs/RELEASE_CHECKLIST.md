# Release Checklist

Use this checklist before pushing a portfolio/public-demo release.

## Code Quality

- Run the local release gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

- Full test suite passes:

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

- Public branding audit passes and reports only approved compatibility identifiers:

```powershell
.venv\Scripts\python scripts\brand_audit.py
```

- JavaScript syntax passes:

```powershell
node --check apps\web\app.js
node --check apps\web\mock-api.js
node --check apps\web\application-intake.js
node --check apps\web\portfolio-dashboard.js
node --check apps\web\risk-detail.js
node --check scripts\static-demo-smoke.js
node --check scripts\frontend-workflow-smoke.js
node --check scripts\application-intake-smoke.js
node --check scripts\portfolio-dashboard-smoke.js
```

- Application intake smoke test passes:

```powershell
node scripts\application-intake-smoke.js
```

- Portfolio dashboard smoke test passes:

```powershell
node scripts\portfolio-dashboard-smoke.js
```

- Static demo smoke test passes:

```powershell
node scripts\static-demo-smoke.js
```

- Frontend workflow smoke test passes:

```powershell
node scripts\frontend-workflow-smoke.js
```

- PostgreSQL migration smoke dry run passes locally:

```powershell
.venv\Scripts\python scripts\postgresql-migration-smoke.py --dry-run
```

- PostgreSQL recovery smoke dry run passes locally:

```powershell
.venv\Scripts\python scripts\postgresql-backup-restore-smoke.py --dry-run
```

- Live API workflow smoke test passes against a temporary SQLite database:

```powershell
.venv\Scripts\python scripts\live-api-workflow-smoke.py
```

- CI runs that same live HTTP workflow with
  `MICROSCORE_STORAGE_BACKEND=postgresql` against disposable PostgreSQL 16.
- CI then dumps the populated database, restores it into a clean database,
  compares all 12 table fingerprints and the active-model invariant, and
  confirms restore-target cleanup.
- CI audits the installed Python dependency graph with `pip-audit`; Dependabot
  checks pip, Docker, and GitHub Actions inputs weekly.
- Deployment Candidate configuration has an automated clean-stack proof:

```powershell
docker compose config --quiet
docker compose up --build --detach
```

  Verify `http://127.0.0.1:8010/health` reports `postgresql`, then clean up with
  `docker compose down --volumes --remove-orphans`.

- Live security workflow smoke test passes against a temporary SQLite database:

```powershell
.venv\Scripts\python scripts\live-security-workflow-smoke.py
```

- HTTP observability/performance regression gate passes locally:

```powershell
.venv\Scripts\python scripts\http-performance-smoke.py --dry-run
.venv\Scripts\python scripts\http-performance-smoke.py --requests 160 --concurrency 8 --p95-budget-ms 750 --min-throughput-rps 15
```

  Confirm `X-Request-ID` propagation, `Server-Timing`, zero 5xx responses,
  client p95 within 750 ms, and throughput of at least 15 requests/second.
  CI repeats the same bounded workload in the separate
  `observability-performance` job against disposable PostgreSQL 16 with a
  1,200 ms p95 budget for shared-runner and database-network variability.
  These environment-specific thresholds are regression budgets, not a backend
  comparison, production SLO, or production capacity claim.

- Git diff has no whitespace errors:

```powershell
git diff --check
```

## Release Gate Traceability

- `docs/ENGINEERING_QUALITY.md` includes the Release Gate Matrix v1.
- `docs/ENGINEERING_QUALITY.md` includes the Security Readiness Gate Matrix v1.
- `docs/RELEASE_CANDIDATE.md` defines the reviewer-ready freeze boundary and
  the claims that remain blocked.
- Every product, security, and research promise in the matrix points to a real
  test or smoke script plus key markers that must stay covered.
- Matrix drift is checked by:

```powershell
.venv\Scripts\python -m unittest tests.test_release_gate_matrix
```

## Submission Integrity

- `reports/submission/manifest.json` is generated only after the public pages,
  documentation, research artifacts, PDFs, tests, and release scripts are
  final.
- The manifest records synchronized quality counts, explicit limitations, and
  SHA-256 hashes for the critical reviewer-facing evidence set.
- The deterministic manifest check passes without rewriting any artifact:

```powershell
.venv\Scripts\python scripts\build-submission-manifest.py --check
```

- Submission-readiness checks pass:

```powershell
.venv\Scripts\python -m unittest tests.test_submission_readiness
```

## Public Reviewer Experience

- The three public entry points load only repository-local assets and keep every
  local link valid; README and Project Brief links also resolve.
- The reviewer home shows the main negative result, public benchmark, quality
  evidence, and non-production boundary before asking for a deep technical read.
- Public markup and cache versions use neutral engineering-review language,
  without admissions-specific positioning.
- Reviewer home, evidence hub, and walkthrough do not produce page-level
  horizontal scroll at desktop, tablet, or narrow mobile widths. Manual browser
  QA covers 1440, 1024, 768, 390, and 320 CSS-pixel viewports.
- Inactive walkthrough scenes use the native `hidden` contract and cannot
  remain rendered off-canvas; public stylesheets do not impose a fixed 320 px
  minimum width that conflicts with a visible vertical scrollbar.
- Reviewer home, evidence hub, and walkthrough expose keyboard-visible skip
  links to their main content and retain visible focus treatment.
- The walkthrough implements the ARIA tab/tab-panel relationship, keeps only
  the active scene in the focus order, and supports roving arrow-key focus.
- All three public stylesheets respect reduced-motion preferences; an autoplay
  query does not start automatically when reduced motion is requested.
- Tracked files exclude databases, private keys, `.env`, virtual environments,
  caches, and notebook checkpoints.
- CI and the local release gate run:

```powershell
.venv\Scripts\python scripts\reviewer-experience-smoke.py
```

## Technical Defense Gate

- `docs/TECHNICAL_INTERVIEW_GUIDE.md` covers the central modeling, evaluation,
  policy, Monte Carlo, architecture, governance, and pilot-boundary questions.
- `reports/submission/technical-defense.json` contains 12 evidence-backed
  questions, three timed rehearsal routes, follow-ups, prohibited claims, and a
  manual scorecard.
- Its five headline metrics are recomputed from the committed research and
  benchmark CSV files instead of being trusted as free-form prose.
- The deterministic defense check passes before the submission manifest check:

```powershell
.venv\Scripts\python scripts\build-technical-defense-packet.py --check
```

- Automation must keep `oral_understanding_verified` false and the packet status
  `owner_rehearsal_required`; only an unscripted rehearsal can close that human
  ownership step.

- Both PDFs have been rendered and visually reviewed after their final build.
- The release remains `review_ready_not_production_ready`; a clean manifest is
  a consistency control, not production validation or a cryptographic release
  signature.

## Demo Safety

- Static demo warning is visible.
- Borrower submission requires the synthetic-data consent checkbox.
- Invalid borrower fields are highlighted with a visible summary and are rejected
  by the same intake contract in static mode and the typed API.
- Unknown behavioral fields and district/settlement mismatches return validation
  errors instead of entering the scoring pipeline.
- Auth responses and `/me` expose `session_expires_at` and
  `session_ttl_seconds`; the session pill makes token expiry visible.
- Production identity readiness is explicit: the checklist and gate must keep
  saying that production IdP/TOTP/WebAuthn remains future work before real
  borrower data.
- Staff Invite v3 creates expiring analyst invites, supports admin revocation,
  returns the raw invite token only once at creation time, enforces password
  setup at acceptance time, and records invite creation/acceptance/revocation
  audit events; direct temporary-password provisioning remains prototype-only.
- Staff Invite Health v1 exposes invite rotation health, including expired and
  soon-expiring pending invites, in both the API and static demo.
- Invite Delivery v1 returns a one-time invite URL at creation, records
  audited delivery metadata before active pending invites can pass Security
  Readiness, and emits `staff_invite_delivered` without exposing raw tokens.
- Safe Invite Rotation v1 rotates unused invites instead of resending old raw
  secrets, closes the source invite, returns only the new one-time URL, and
  emits `staff_invite_rotated` with token previews only.
- Invite Delivery Outbox v1 persists delivery attempts, supports optional
  local outbox delivery during create/rotate, exposes attempt history to admins,
  and emits `staff_invite_delivery_attempted` without storing raw tokens.
- Invite Delivery Retry v1 adds explicit local provider outcomes
  (`local_outbox`, `local_queue`, `local_fail`, `manual_receipt`), failed-attempt
  Security Readiness warnings, and a retry endpoint that appends attempts
  without re-exposing raw invite tokens.
- Invite Delivery Readiness v2 exposes
  `/admin/staff-invites/delivery-readiness`, provider profile modes,
  HTTPS/non-local invite URL checks, transactional email secret/configuration
  readiness (`MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY`, sender, template, and
  webhook secret), active undelivered invite blockers, and a clear limitation
  that the prototype adapter records attempts without sending external email.
- Transactional Delivery Adapter Boundary v1 exposes
  `/admin/staff-invites/delivery-adapter-readiness`, blocks external sends by
  design, reports `external_send_adapter_disabled`,
  `invite_secret_material_not_available`, secret-rotation readiness, safe vs
  forbidden payload fields, webhook correlation fields, and the
  `adapter_idempotency_key` strategy without exposing secret values.
- Invite Delivery Webhook v1 exposes signed
  `/webhooks/staff-invite-delivery`, HMAC/timestamp replay protection,
  provider-event idempotency, admin-visible `/delivery-events`, delivery/bounce
  status mapping, and `staff_invite_delivery_webhook_received` audit evidence
  without exposing raw invite tokens or webhook secrets.
- Invite Delivery Worker v1 exposes
  `/admin/staff-invites/delivery-outbox` and
  `/admin/staff-invites/delivery-outbox/run`, persists worker status on
  attempts (`queued`, `retry_scheduled`, `completed`, `dead_letter`),
  supports dry-run/retry/dead-letter handling, emits
  `staff_invite_delivery_worker_run` with safe `adapter_idempotency_keys`, and
  clearly states that the prototype worker does not send messages through an
  external provider.
- MFA Enforcement v1 exposes active staff MFA posture, supports admin
  attestation, requires the prototype second-factor code for staff sessions,
  records `staff_mfa_attested` and `staff_mfa_login_verified`, and clearly
  states that production IdP/TOTP/WebAuthn remains future work.
- MFA Challenge Monitoring v1 records failed staff MFA challenges without raw
  codes and raises a Security Readiness warning for recent failed challenges.
- Security Readiness v1 aggregates MFA posture, invite hygiene, audited invite
  delivery, session TTL, and remaining production caveats into a pre-pilot
  admin gate.
- Pre-Pilot Readiness Gate v1 exposes
  `/admin/governance/pre-pilot-readiness`, aggregates security, identity,
  transactional delivery, storage, model, Monte Carlo, review-flow, privacy,
  and tenant-isolation evidence, keeps `production_data_allowed=false` while
  blockers or warnings remain, and separates public demo readiness from real
  borrower pilot permission.
- PostgreSQL Runtime v1 exposes
  `/admin/storage/postgresql-readiness`, schema inventory, JSON-column mapping
  coverage, the versioned `migrations/postgresql/0001_initial_schema.sql`,
  tenant-scope parity checks, disposable migration-smoke CI evidence through
  `scripts/postgresql-migration-smoke.py`, executable runtime parity through
  `scripts/postgresql-runtime-smoke.py`, and the fully grouped
  `microscore_api.postgres_repository` adapter v10
  (`runtime_backend_v1`, 52 implemented methods out of 52, seven completed
  method groups). The same borrower-to-decision HTTP workflow runs against
  SQLite locally and PostgreSQL in CI. SQLite remains the default; a SQLite process still reports a
  missing `MICROSCORE_DATABASE_URL` without exposing secret values.
- Deployment Candidate v1 builds non-root API/web images, keeps the database
  port internal, runs migration and seed as one-shot jobs, health-gates service
  order, and is rebuilt from a clean Compose stack in CI. It remains synthetic
  and does not make `production_data_allowed` true.
- PostgreSQL Recovery Gate v1 proves a credential-safe custom-format
  dump/restore cycle against disposable PostgreSQL, exact source/restore table
  fingerprints, migration/model invariants, and cleanup. It does not claim
  managed backups, retention, point-in-time recovery, or measured RPO/RTO.
- Supply-Chain Gate v1 runs a strict installed-environment vulnerability audit
  and weekly dependency update discovery. Lockfiles with hashes, retained SBOM,
  signing/provenance, and deployment digest pinning remain future controls.
- Storage readiness remains explicit: SQLite is the prototype backend,
  while PostgreSQL can be selected for the same repository contract. No release
  should imply managed-production storage readiness until database deployment,
  managed backup/restore, retention, monitoring, least-privilege roles, secret
  rotation, and measured operational recovery have been validated.
- Staff/User Lifecycle v1 disables MFI analyst accounts without deletion,
  revokes active sessions, rejects future login, and records
  `staff_user_disabled`.
- Staff/User Lifecycle v2 reactivates disabled MFI analysts without creating a
  session automatically and records `staff_user_reactivated`.
- Staff Session Control v1 lists active staff sessions without raw bearer
  tokens, protects the current admin session, and records
  `staff_session_revoked` for targeted revocation.
- Borrower history lists only the signed-in account's applications and excludes
  internal scores, analyst identity, and review notes.
- Lifecycle transitions preserve `under_review` during re-scoring and reject
  mutations after `approved` or `declined`.
- Risk Detail loads automatically and shows lifecycle actions, affordability
  completeness, governance checks, and chronological decision history.
- Affordability output states that it is screening context, not a verdict.
- MFI score detail and review packet show the model-use notice.
- Portfolio Overview shows risk bands, district risk, settlement mix, policy
  mix, analyst decisions, and the screenshot snapshot note.
- Admin model registry shows exactly one active version.
- Activating a candidate marks older review packets as stale until re-scored.
- Monte Carlo output says scenario planning, not forecast or borrower score.
- Repeating a run with the same seed produces identical scenario distributions.
- Repeated runs preserve a stable 64-character portfolio fingerprint.
- Simulation history can reopen the exact stored result and remains tenant-scoped.
- Monte Carlo standard-error diagnostics are present and nonnegative.
- Adverse/severe defaults do not improve relative to baseline for paired draws.
- Demo accounts use synthetic data only.
- No real borrower names, phone numbers, IINs, addresses, or bank records are
  present.
- README clearly states that synthetic data is not real-world lending
  validation.

## Public Demo

- GitHub Pages source is set to **GitHub Actions**.
- `Deploy static web demo` workflow succeeds.
- Public demo opens without FastAPI.
- Hosted page automatically uses static demo mode.
- Hosted/static demo hides local API settings from the reviewer-facing sidebar.
- `Reset demo` restores the synthetic portfolio.
- MFI queue, score detail, review packet, and analytics show clear loading,
  empty, and error states.
- Portfolio dashboard charts are populated from synthetic scored applications
  and do not imply real regional calibration.

## Reviewer Assets

- Login screen reviewer snapshot is visible and current.
- README Snapshot is current.
- Demo Walkthrough is current.
- Demo Video Script is current.
- Screenshot Checklist is current.
- Public Demo Plan is current.
- Model Card and Data Statement still match the implementation.
- Research Paper draft mentions the latest limitations and findings.

## Final Manual Check

Open the public or local static demo and verify:

1. Login page is the first visible screen.
2. Borrower can submit a demo application.
3. MFI analyst can view queue, score detail, review packet, and analytics.
4. Admin can view audit trail and clear/reset demo state.
5. No screen invites users to submit real personal data.
6. Screenshots and demo video use only synthetic/demo data.
