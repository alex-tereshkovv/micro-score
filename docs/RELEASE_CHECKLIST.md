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

- Live API workflow smoke test passes against a temporary SQLite database:

```powershell
.venv\Scripts\python scripts\live-api-workflow-smoke.py
```

- Live security workflow smoke test passes against a temporary SQLite database:

```powershell
.venv\Scripts\python scripts\live-security-workflow-smoke.py
```

- Git diff has no whitespace errors:

```powershell
git diff --check
```

## Release Gate Traceability

- `docs/ENGINEERING_QUALITY.md` includes the Release Gate Matrix v1.
- `docs/ENGINEERING_QUALITY.md` includes the Security Readiness Gate Matrix v1.
- Every product, security, and research promise in the matrix points to a real
  test or smoke script plus key markers that must stay covered.
- Matrix drift is checked by:

```powershell
.venv\Scripts\python -m unittest tests.test_release_gate_matrix
```

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
- PostgreSQL Migration Readiness v1 exposes
  `/admin/storage/postgresql-readiness`, schema inventory, JSON-column mapping
  coverage, the reviewed `migrations/postgresql/0001_initial_schema.sql` draft,
  tenant-scope parity checks, disposable migration-smoke CI evidence through
  `scripts/postgresql-migration-smoke.py`, the partial method-groups
  `microscore_api.postgres_repository` adapter v5
  (`model_registry_audit_organizations_groups_v1`, 11 implemented methods out
  of 52, three completed method groups), missing
  `MICROSCORE_DATABASE_URL`, and blockers for the unimplemented PostgreSQL
  repository backend and repository-level PostgreSQL parity CI.
- Storage readiness remains explicit: SQLite is the prototype backend,
  PostgreSQL migration remains blocked/planned even with the 0001 draft,
  migration-smoke CI, and completed model registry, audit, and organization
  adapter groups present, and no release should imply production storage
  readiness until a real backend, managed database connection, production
  migration runner, and repository parity CI gate exist.
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
