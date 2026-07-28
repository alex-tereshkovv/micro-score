# Engineering Quality

MicroScore is a research and product prototype, so the quality goal is not only
model performance. The project should remain reproducible, reviewable, and safe
to demo as the codebase grows.

## Local Checks

Use the local check script on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

It runs:

- unit and integration tests
- Python syntax compilation
- research pipeline smoke test
- regional decision smoke test

## Release Gate Matrix v1

This matrix maps product, security, and research promises to the checks that
prove them. A release should not claim a promise unless its row has a passing
automated proof in the local gate or an explicitly documented manual follow-up.

| Promise area | Primary proof | Key markers that must stay covered |
| --- | --- | --- |
| Auth/session expiry and logout | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py` | `session_expires_at`, `session_ttl_seconds`, `/auth/logout`, `session_expiry_visible`, `logout_guard` |
| Staff invites and delivery hygiene | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py` | `/admin/staff-invites`, `/auth/accept-staff-invite`, `staff_invite_delivery_attempted`, `staff_invite_rotated`, `staff_invite_token_hygiene` |
| MFA enforcement and readiness | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py` | `/admin/security/mfa-readiness`, `staff_mfa_attested`, `staff_mfa_login_verified`, `staff_mfa_challenge_failed`, `mfa_readiness` |
| Staff sessions and lifecycle controls | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py` | `/admin/staff-sessions`, `staff_session_revoked`, `staff_user_disabled`, `staff_user_reactivated`, `staff_session_control` |
| Tenant isolation | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_research_docs.py` | `organization_id`, `cross-tenant detail access returns 403`, `tenant_isolation`, `/admin/organizations` |
| Borrower lifecycle and borrower-safe projection | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `scripts/frontend-workflow-smoke.js`, `tests/test_research_docs.py` | `BorrowerApplicationResponse`, `borrower-safe`, `lifecycle_terminal_guard`, `terminal_locked`, `score_result` |
| Review action plan and risk detail readiness | `tests/test_api_integration.py`, `scripts/static-demo-smoke.js`, `scripts/frontend-workflow-smoke.js`, `tests/test_web_static.py` | `buildReviewActionPlan`, `score_first`, `review_or_decide`, `finalize_decision`, `action_plan_terminal` |
| Monte Carlo portfolio simulation | `tests/test_api_integration.py`, `tests/test_api_database.py`, `tests/test_api_simulation.py`, `scripts/static-demo-smoke.js`, `tests/test_research_docs.py` | `portfolio_fingerprint`, `calibration_volatility`, `Monte Carlo standard errors`, `simulation_history`, `portfolio_simulation_run` |
| Model registry and stale-score governance | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_research_docs.py` | `/admin/model-versions`, `stale_model_version`, `model_registry`, `active_model`, `immutable governance snapshot` |
| Pre-pilot release readiness gate | `tests/test_api_integration.py`, `scripts/static-demo-smoke.js`, `scripts/live-security-workflow-smoke.py`, `tests/test_web_static.py`, `docs/RELEASE_CHECKLIST.md` | `/admin/governance/pre-pilot-readiness`, `PrePilotReadinessResponse`, `production_data_allowed`, `public_demo_allowed`, `pre_pilot_readiness_gate` |
| Privacy intake and sensitive-field rejection | `tests/test_api_integration.py`, `tests/test_api_privacy.py`, `scripts/application-intake-smoke.js`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py` | `consent_confirmed`, `borrower_consent`, `find_forbidden_signal_paths`, `privacy_guards`, `Unexpected behavioral field` |
| Research documentation boundaries | `tests/test_research_docs.py`, `tests/test_reporting.py`, `tests/test_modeling.py`, `docs/RELEASE_CHECKLIST.md` | `synthetic data is not real-world lending`, `Model Card and Data Statement`, `calibration volatility`, `Monte Carlo portfolio simulation`, `research_governance_docs_exist` |

The matrix is enforced by `tests/test_release_gate_matrix.py`, which verifies
that each matrix row references real test or smoke files and that its key
markers still exist in the named proof artifacts.

## Security Readiness Gate Matrix v1

This security-specific matrix keeps pilot-readiness claims separate from
production-readiness claims. A release can be called demo-ready only when these
checks pass, and it must continue to say what remains blocked before real
borrower data or production onboarding.

| Security promise | Primary proof | Required security markers |
| --- | --- | --- |
| Production identity readiness is explicit, not complete | `tests/test_api_integration.py`, `tests/test_research_docs.py`, `scripts/static-demo-smoke.js`, `docs/RELEASE_CHECKLIST.md` | `not a completed production security review`, `production IdP/TOTP/WebAuthn remains future work`, `/admin/security/readiness`, `security_readiness` |
| Invite delivery mode is audited and local-only by default | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py`, `docs/RELEASE_CHECKLIST.md` | `/admin/staff-invites/delivery-readiness`, `/admin/staff-invites/delivery-adapter-readiness`, `/admin/staff-invites/delivery-outbox`, `/admin/staff-invites/delivery-outbox/run`, `/webhooks/staff-invite-delivery`, `staff_invite_delivery_webhook_received`, `staff_invite_delivery_worker_run`, `delivery_provider_not_production_ready`, `delivery_provider_configuration_missing`, `MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY`, `transactional_email_contract`, `external_send_adapter_disabled`, `adapter_idempotency_key`, `dead_letter`, `local_outbox`, `staff_invite_delivery_retry` |
| MFA and staff-session lifecycle are proven end to end | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/static-demo-smoke.js`, `tests/test_web_static.py` | `staff_mfa_login_verified`, `staff_mfa_challenge_failed`, `/admin/staff-sessions`, `staff_session_revoked`, `staff_user_disabled` |
| Storage assumptions remain visible before pilot use | `tests/test_api_integration.py`, `tests/test_api_database.py`, `scripts/live-api-workflow-smoke.py`, `scripts/live-security-workflow-smoke.py`, `scripts/postgresql-migration-smoke.py`, `scripts/static-demo-smoke.js`, `.github/workflows/ci.yml`, `tests/test_web_static.py`, `migrations/postgresql/0001_initial_schema.sql`, `docs/RELEASE_CHECKLIST.md` | `/admin/storage/postgresql-readiness`, `PostgresMigrationReadinessResponse`, `storage_readiness`, `postgresql_schema_inventory`, `postgresql_versioned_migration_artifacts`, `postgresql_disposable_migration_ci`, `disposable_migration_ci_present`, `0001_initial_schema`, `migration_artifact_count`, `postgres:16`, `postgresql_disposable_ci`, `MICROSCORE_STORAGE_BACKEND`, `production_ready`, `temporary-sqlite`, `PostgreSQL` |
| Live security workflow stays inside the release gate | `scripts/check.ps1`, `scripts/live-api-workflow-smoke.py`, `scripts/live-security-workflow-smoke.py`, `tests/test_github_workflows.py`, `docs/RELEASE_CHECKLIST.md` | `Live API workflow smoke test`, `Live security workflow smoke test`, `scripts\live-security-workflow-smoke.py`, `temporary-sqlite`, `session_preview`, `token_preview` |
| No-overclaim limitations remain release blockers | `tests/test_research_docs.py`, `docs/RELEASE_CHECKLIST.md`, `docs/ENGINEERING_QUALITY.md` | `synthetic data is not real-world lending`, `No real borrower`, `production IdP/TOTP/WebAuthn remains future work`, `SQLite`, `not ready for real loan approval` |

The same drift test verifies this matrix. If a marker or proof artifact is
removed, the security-readiness gate should fail before a reviewer has to infer
whether the release is still pilot-safe.

## Static Demo Smoke Test

The shared borrower intake contract has a focused Node test:

```powershell
node scripts\application-intake-smoke.js
```

It verifies accepted input plus amount boundaries, district/settlement
consistency, whole-number counts, unknown-signal rejection, and consent.

The Portfolio Dashboard v2 summary has a focused Node test:

```powershell
node scripts\portfolio-dashboard-smoke.js
```

It verifies risk-band counts, district risk ordering, top-district
concentration, settlement-type ordering, rural/peri-urban contextual share, and
static demo seed-data consistency.

The public-demo layer has its own Node smoke test:

```powershell
node scripts\static-demo-smoke.js
```

The smoke test verifies that the in-browser static backend can:

- sign in as an MFI analyst
- verify auth/session expiry metadata in the static contract
- create, revoke, and accept expiring staff invites with password-policy
  enforcement and one-time raw token handling
- record audited invite delivery metadata and verify undelivered active pending
  invites block Security Readiness until delivery is marked
- persist delivery attempts, verify manual receipts and local outbox attempts,
  and ensure attempt rows/audit events never expose raw invite tokens
- simulate failed local invite delivery, verify Security Readiness warning,
  retry with a working provider, and confirm raw invite tokens remain hidden
- verify the transactional delivery adapter boundary remains blocked by design,
  exposes safe/forbidden payload fields, and carries `adapter_idempotency_key`
  without exposing raw invite tokens or provider secrets
- run the audited invite delivery worker outbox, verify due queued attempts,
  dead-letter exhausted local queue attempts, and confirm worker audit events
  never expose raw invite tokens
- rotate unused staff invites as the safe resend path, verify the old raw token
  is revoked, and assert `staff_invite_rotated` contains previews rather than
  raw secrets
- summarize staff invite rotation health and flag soon-expiring pending invites
- summarize staff MFA readiness, record pilot attestation, and verify the
  `staff_mfa_attested` audit event plus login-time prototype MFA enforcement
- reject failed staff MFA challenges, verify `staff_mfa_challenge_failed`
  audit events hide raw codes, and confirm Security Readiness warning
- aggregate MFA posture, invite hygiene, audited invite delivery, session TTL,
  and known production blockers in Security Readiness v1
- list active staff sessions without raw bearer tokens, reject current-session
  self-revocation, revoke another staff session, and verify `staff_session_revoked`
- disable an MFI analyst, revoke their active static session, reject future
  login, and verify the `staff_user_disabled` audit event
- reactivate the analyst, verify login resumes without automatic session
  creation, and verify the `staff_user_reactivated` audit event
- load the seeded application queue
- score an application
- open a review packet
- list borrower-safe application history and complete a guarded lifecycle from
  submission through review to a terminal decision
- switch the active model registry version and detect a stale score
- re-score with the newly active model and preserve its governance snapshot
- reproduce a seeded Monte Carlo run and verify worsening stress scenarios do
  not reduce simulated default counts
- verify simulation fingerprint stability, standard-error diagnostics, and
  stored history/detail parity
- verify Portfolio Dashboard v2 district and settlement summary rows
- load policy analytics
- export a CSV sample
- reset the static demo portfolio

The dedicated frontend workflow contract test is:

```powershell
node scripts\frontend-workflow-smoke.js
```

It exercises the static API together with the shared Risk Detail view-model:
borrower-safe history, affordability completeness, manual-review transition,
chronological decision history, and terminal-state locking.

## GitHub Actions CI

The CI workflow is defined in:

```text
.github/workflows/ci.yml
```

It runs on pushes and pull requests to `main` and checks:

- Python dependency installation
- full test suite
- Python syntax compilation
- research smoke test
- regional decision smoke test
- frontend JavaScript syntax
- application intake contract smoke test
- portfolio dashboard smoke test
- static demo smoke test

## Deployment Gate

The GitHub Pages workflow is defined in:

```text
.github/workflows/pages.yml
```

It deploys only the static `apps/web/` demo. No real borrower data, SQLite
database, trained model artifacts, or backend secrets are deployed.
