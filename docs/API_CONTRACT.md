# MicroScore API Contract

This document describes the current backend contract for the MicroScore product
prototype. It is intended to guide the future borrower frontend and MFI analyst
dashboard.

## Local Run

Install app dependencies:

```powershell
.venv\Scripts\python -m pip install -e ".[app]"
```

Seed demo data:

```powershell
.venv\Scripts\python -m microscore_api.seed
```

The seed command creates the main demo users and a scored portfolio of 20
Pavlodar-region applications so the MFI queue, segment analytics, and Policy
Lab have data immediately.

Run the API:

```powershell
.venv\Scripts\python -m uvicorn microscore_api.main:app --reload
```

Run the web UI in another PowerShell window:

```powershell
.venv\Scripts\python -m http.server 5173 --directory apps\web
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Open the frontend:

```text
http://127.0.0.1:5173
```

## Pilot Governance Contract

Pilot-readiness contract:

```http
GET /governance/pilot-readiness
```

This public read-only endpoint describes the minimum-data plan for a future
supervised Pavlodar pilot. It returns:

- data classes that may be collected in a pilot;
- whether each class is a model input, audit-only field, or not used by the
  model;
- forbidden data such as IINs, raw bank statements, precise geolocation, and
  biometric data;
- validation questions for an MFI partner;
- first-pilot success criteria.

The endpoint does not expose borrower data. It exists so the API contract makes
MicroScore's privacy boundary explicit.

## Roles

- `borrower`: can create and view own loan applications.
- `mfi_analyst`: can view all applications, score applications, and view
  segment and policy analytics within the assigned MFI organization.
- `admin`: can do MFI analyst actions and view audit events.

List organizations available for borrower applications:

```http
GET /organizations
```

Create an organization as global admin:

```http
POST /admin/organizations
```

Applications, MFI queues, review packets, CSV exports, and analytics are scoped
by `organization_id`. Global admins can inspect all organizations; analysts can
access only applications assigned to their organization.

The web client loads this directory dynamically. Borrower application and staff
provisioning selects are refreshed from `GET /organizations`; global admins can
create a tenant and immediately assign analysts without editing frontend code.

Demo users:

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
staff/admin MFA code: 246810
```

## Authentication

Register:

```http
POST /auth/register
```

Request:

```json
{
  "email": "borrower@test.com",
  "password": "password123",
  "role": "borrower"
}
```

Public registration creates borrower accounts only. Requests that attempt to
self-assign `mfi_analyst` or `admin` are rejected. MFI analysts are provisioned
by an existing administrator; additional administrators remain a
deployment-level operation.

New registration passwords must contain at least 10 characters, uppercase and
lowercase letters, a number, and a symbol. Common passwords are rejected. The
seeded demo accounts keep `password123` for reviewer convenience; this is demo
data and not the production password policy.

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "role": "borrower",
  "organization_id": null,
  "session_expires_at": "2026-06-24T20:00:00+00:00",
  "session_ttl_seconds": 28800
}
```

All protected endpoints use:

```http
Authorization: Bearer <access_token>
```

Sessions expire after 8 hours by default. Override the duration for a deployed
environment with:

```powershell
$env:MICROSCORE_SESSION_TTL_HOURS = "4"
```

`POST /auth/register`, `POST /auth/login`, and `GET /me` return the current
session expiry metadata through `session_expires_at` and
`session_ttl_seconds`, so the browser can make token lifetime visible instead
of treating sessions as indefinite.

Staff login (`admin` and `mfi_analyst`) now requires both recorded MFA
attestation and a second-factor code in the login payload:

```json
{
  "email": "analyst@test.com",
  "password": "password123",
  "mfa_code": "246810"
}
```

The default local prototype MFA code is `246810`; override it for local
deployment experiments with `MICROSCORE_PROTOTYPE_MFA_CODE`. This is a
prototype control for reviewer/pilot readiness, not a replacement for a
production identity provider, TOTP/WebAuthn enrollment, or recovery flows.

Logout and revoke the current token:

```http
POST /auth/logout
```

The browser API accepts CORS requests only from the local frontend and the
MicroScore GitHub Pages origin by default. Additional deployed frontend origins
can be supplied as a comma-separated list:

```powershell
$env:MICROSCORE_CORS_ORIGINS = "https://demo.example.org,https://mfi.example.org"
```

These controls improve the prototype boundary, but they are not a replacement
for a production identity provider, HTTPS, distributed rate limiting, or a
formal security review.

Login currently has a small in-memory limiter: five failed attempts within one
minute block that client/account key for five minutes and return `429` with a
`Retry-After` header. This protects the single-process prototype only. A
multi-instance deployment should move the limiter to Redis or a managed
identity provider.

## Admin Staff Provisioning

List public user records:

```http
GET /admin/users
```

Create an MFI analyst account:

```http
POST /admin/users
```

```json
{
  "email": "analyst@mfi.example",
  "password": "TemporaryPass1!",
  "role": "mfi_analyst",
  "organization_id": "pavlodar-demo-mfi"
}
```

Both endpoints require an `admin` bearer token. The create endpoint accepts
only `mfi_analyst`; additional administrators remain a deployment-level
operation. Password hashes are never returned. Successful provisioning records
a `staff_user_created` audit event with the acting administrator.

Disable an MFI analyst account without deleting its history:

```http
POST /admin/users/{email}/disable
```

The disable endpoint requires an `admin` bearer token and only applies to
`mfi_analyst` accounts. It sets `disabled_at`/`disabled_by`, revokes all active
sessions for that analyst, rejects future login with `Account disabled`, and
records `staff_user_disabled`. Repeating the request is idempotent and returns
`was_already_disabled: true`.

Reactivate a disabled MFI analyst account:

```http
POST /admin/users/{email}/reactivate
```

The reactivation endpoint requires an `admin` bearer token, only applies to
`mfi_analyst` accounts, clears `disabled_at`/`disabled_by`, and records
`staff_user_reactivated` with the previous disable metadata. It does not create
a session automatically; the analyst must sign in again with their existing
password. Repeating the request is idempotent and returns
`was_already_active: true`.

List and revoke active staff sessions:

```http
GET /admin/staff-sessions
DELETE /admin/staff-sessions/{session_id}
```

Both endpoints require an `admin` bearer token. The list endpoint returns active
`admin` and `mfi_analyst` sessions only, with `session_id` as a SHA-256 hash of
the bearer token, `session_preview`, `email`, `role`, `organization_id`,
`session_created_at`, `session_expires_at`, `session_ttl_seconds`, and
`is_current_session`. It never returns raw bearer tokens and omits borrower
sessions. Deleting a session revokes that one staff session and records
`staff_session_revoked` with safe session preview metadata. The current admin
session is protected from this endpoint; use `/auth/logout` to revoke it.

MFA readiness and attestation:

```http
GET /admin/security/readiness
GET /admin/security/identity-readiness
GET /admin/security/mfa-readiness
POST /admin/users/{email}/mfa/attest
```

These endpoints require an `admin` bearer token. Security Readiness v1 combines
MFA posture, invite hygiene, audited invite delivery, session lifetime, and
remaining production caveats into one pre-pilot gate. It returns `status`,
`blockers_count`, `warnings_count`, structured `checks`,
`recommended_actions`, and a `limitation` stating that this is not a completed
production security review.

Identity Readiness v1 is a narrower admin-only review surface for production
identity assumptions. It returns stable provider/mode fields plus component
rows with `key`, `status`, `severity`, `summary`, and `action`. It summarizes:

- current local password-auth provider mode;
- invite delivery provider mode;
- staff MFA attestation and prototype-code posture;
- staff session inventory/revoke posture;
- in-memory rate-limit assumptions;
- storage readiness assumptions;
- tenant isolation posture;
- production blockers and next required controls.

The endpoint is intentionally blocked for production while MicroScore uses local
password auth, prototype shared-code MFA, in-memory rate limiting, local invite
delivery, and SQLite storage. It does not return raw passwords, raw invite
tokens, bearer tokens, session ids, MFA codes, or borrower-private review data.
It is not a completed production security review.

MFA Readiness v2 records admin attestation for active `admin` and
`mfi_analyst` accounts and the local prototype requires a second-factor code
for staff sessions. The MFA readiness response is `blocked` while active staff
accounts lack attestation and includes `missing_mfa_count`,
`mfa_attested_count`, account-level status rows, a `recommended_action`, and a
`limitation` stating that the prototype code is not a production identity
provider. Successful first-time attestation records `staff_mfa_attested`;
repeated attestation is idempotent and returns `was_already_attested: true`.
Successful staff login records `staff_mfa_login_verified`.
Failed staff MFA challenges record `staff_mfa_challenge_failed` without storing
the submitted code. The audit details include `reason` (`missing_attestation`,
`missing_code`, or `invalid_code`), `source` (`login` or
`staff_invite_acceptance`), `mfa_code_present`, method, and prototype
limitation metadata.

In Security Readiness v1, `mfa_enforcement` is `pass` when staff login requires
both attestation and the prototype code. `mfa_challenge_failures` is a warning
when failed staff MFA challenges were recorded in the last 24 hours.
`invite_delivery` is `pass` when there are no active pending staff invites, or
when every active pending invite has audited delivery metadata with an HTTPS URL
base or a local-development HTTP base. It is a blocker while an active pending
invite has not been marked delivered, or when a delivered invite records an
unsafe non-local HTTP base. The
`invite_delivery_attempts` check is a warning when an active pending invite's
latest delivery attempt failed, so operators can retry delivery before sharing
the onboarding link. The recommended actions still point to production
IdP/TOTP/WebAuthn replacement and transactional delivery before real user data.

The temporary-password flow remains as a prototype/admin fallback. The safer
default for new staff is Staff Invite v3: administrators create an expiring
invite, can revoke it before use, and the analyst sets their own password
during acceptance. The raw invite token is a one-time secret: it is returned
only from invite creation and is not returned by invite listing, revocation
responses, or audit events.

List staff invites:

```http
GET /admin/staff-invites
```

Summarize invite rotation health:

```http
GET /admin/staff-invites/health
```

The health endpoint requires an `admin` bearer token and returns a computed
summary for invite hygiene: `active_pending_count`, `expiring_soon_count`,
`expired_pending_count`, `accepted_count`, `revoked_count`,
`action_required_count`, `oldest_pending_created_at`, `next_expiring_at`, and a
`recommended_action`. The current warning window is 24 hours, and the response
status is `attention` when pending invites are expired or expiring inside that
window.

Summarize invite delivery provider readiness:

```http
GET /admin/staff-invites/delivery-readiness
```

The delivery-readiness endpoint requires an `admin` bearer token and returns a
typed provider contract summary: `configured_provider`, `default_provider`,
`invite_url_base`, `invite_url_https`, `invite_url_local`,
`active_pending_invite_count`, `undelivered_active_invite_count`,
`failed_latest_attempt_count`, `providers`, `production_blockers`, `warnings`,
`next_required_controls`, and `limitation`.

Provider profiles expose `provider`, `attempt_status`, `mode`, `configured`,
`production_ready`, `sends_message`, `audit_only`,
`requires_https_invite_url`, `requires_external_secret`, `summary`, `action`,
and optional `error`. The current local providers (`local_outbox`,
`manual_receipt`, `local_queue`, `local_fail`) are audited prototype modes, not
transactional delivery. `transactional_email` is a contract placeholder only;
the API does not send email, SMS, or secure messages through an external
provider yet. The default production blocker is
`delivery_provider_not_production_ready`; readiness remains `blocked` until the
configured provider is production-ready, invite URLs use a verified HTTPS
non-local origin, and active pending invites have audited delivery evidence.

Create an expiring MFI analyst invite:

```http
POST /admin/staff-invites
```

```json
{
  "email": "analyst@mfi.example",
  "role": "mfi_analyst",
  "organization_id": "pavlodar-demo-mfi",
  "expires_in_hours": 48,
  "queue_delivery": true,
  "delivery_channel": "email",
  "delivery_recipient": "analyst@mfi.example",
  "delivery_provider": "local_outbox"
}
```

`expires_in_hours` can be 1 to 168 hours and defaults to 48. Successful invite
creation records `staff_invite_created` and returns a one-time raw `token`, a
one-time `invite_url`, and safe invite metadata: `token_id`, `token_preview`,
`created_at`, `expires_at`, `accepted_at`, `accepted_by`, `revoked_at`,
`revoked_by`, `delivered_at`, `delivered_by`, `delivery_channel`,
`delivery_recipient`, `delivery_url_base`, `delivery_note`,
`delivery_attempt_count`, `last_delivery_attempt_at`, `last_delivery_status`,
and `last_delivery_provider`.

The raw `token` must be copied at creation time. Later admin list/revoke
responses expose only `token_id`, `token_preview`, and delivery metadata.
The API rejects creation while the same email already has another active
pending staff invite; rotate the existing invite instead.

When `queue_delivery` is `true`, creation records a local delivery attempt while
the raw token is still available in process and returns a `delivery_attempt`
object with `attempt_id`, `provider`, `status`, `channel`, `recipient`,
`delivery_url_base`, timestamps, and optional `error`. The default provider is
`local_outbox`; override it per request with `delivery_provider`, or globally
with `MICROSCORE_INVITE_DELIVERY_PROVIDER` for deployment experiments. Local
provider semantics are explicit: `local_outbox` and `manual_receipt` record
`sent` and mark the invite delivered; `local_queue` records `queued` and leaves
the invite undelivered; `local_fail` records `failed` with an error and leaves
the invite undelivered. Unknown provider names are recorded as `queued` with a
local implementation warning. Delivery attempts never store the raw token or
full invite URL.

Record audited delivery for an active pending invite:

```http
POST /admin/staff-invites/{token_id}/delivery
```

```json
{
  "channel": "manual_copy",
  "recipient": "analyst@mfi.example",
  "note": "Sent through approved onboarding channel"
}
```

Delivery requires an `admin` bearer token and accepts `email`,
`secure_message`, `manual_copy`, or `local_demo` as `channel`. The endpoint
rejects accepted, revoked, and expired invites; otherwise it records
`delivered_at`, `delivered_by`, `delivery_channel`, `delivery_recipient`,
`delivery_url_base`, and `delivery_note`, emits `staff_invite_delivered`, and
returns `was_already_delivered`. Repeating the request is idempotent and does
not overwrite the first delivery record, but every request appends a
`manual_receipt` delivery attempt.

`delivery_url_base` comes from `MICROSCORE_INVITE_WEB_BASE_URL` and defaults to
`http://127.0.0.1:5173` for local development. Non-local bases must be HTTPS.
The static GitHub Pages demo records
`https://alex-tereshkovv.github.io/micro-score` as its delivery base.

List delivery attempts for an invite:

```http
GET /admin/staff-invites/{token_id}/delivery-attempts
```

This returns newest-first `StaffInviteDeliveryAttemptResponse` rows. Attempts
contain the invite `token_id`, provider, status, channel, recipient, URL base,
and optional note/error; they never contain raw tokens.

Retry delivery for an active pending invite:

```http
POST /admin/staff-invites/{token_id}/delivery-attempts/retry
```

```json
{
  "channel": "email",
  "recipient": "analyst@mfi.example",
  "provider": "local_outbox",
  "note": "Retry after failed local provider check"
}
```

Retry requires an `admin` bearer token and rejects accepted, revoked, and
expired invites. It appends a new delivery attempt using the same provider
semantics as queued creation/rotation, returns `was_already_delivered`, and
marks the invite delivered only when the retry attempt is `sent`.

Rotate an unused invite and issue a fresh one-time URL:

```http
POST /admin/staff-invites/{token_id}/rotate
```

```json
{
  "expires_in_hours": 48,
  "queue_delivery": true,
  "delivery_channel": "email",
  "delivery_provider": "local_outbox"
}
```

Rotation requires an `admin` bearer token and is the safe resend path: the API
does not store or re-expose the previous raw token. Accepted invites cannot be
rotated. Pending, expired, or already revoked invites can be rotated; the
source invite is closed with `revoked_at`/`revoked_by` when needed, a new invite
is created for the same email/role/organization, and the response returns only
the new one-time raw `token` and `invite_url`. Rotation records
`staff_invite_created` with `source: "staff_invite_rotation"` and
`staff_invite_rotated` with old/new token previews, not raw tokens.
Rotation is rejected when another active pending invite for the same email
already exists, preventing multiple live onboarding links for one account.
When `queue_delivery` is true, rotation also records a delivery attempt for the
new invite using the configured or requested provider semantics and returns
that attempt in the response.

Revoke an unused invite:

```http
DELETE /admin/staff-invites/{token_id}
```

Revocation requires an `admin` bearer token, records `staff_invite_revoked`,
and returns the updated invite without the raw token. Accepted invites cannot
be revoked. Repeating a revoke for an already revoked invite is idempotent and
returns the existing revoked record.

Accept an invite and set the staff password:

```http
POST /auth/accept-staff-invite
```

```json
{
  "token": "<invite-token>",
  "password": "StrongPassword1!",
  "mfa_code": "246810"
}
```

Acceptance uses the same password policy as registration, rejects expired,
revoked, or already accepted invites, creates an `mfi_analyst` user in the
invite's organization, records `staff_invite_accepted`, records MFA attestation
from invite acceptance, verifies the prototype MFA code, and returns the same
auth response shape as login, including session expiry metadata.

The API stores new invite records by `token_id` instead of the raw token.
Legacy local development invites created before Staff Invite v3 can still be
accepted by their original raw token during migration.

Before any real user data, the production version still needs TOTP/WebAuthn or
an external identity provider and transactional invite delivery.

## Borrower Application Form

Endpoint:

```http
POST /applications
```

Required fields:

- `requested_amount`
- `organization_id`
- `consent_confirmed: true`
- `consent_version`

`behavioral_signals` is an optional typed object so an empty thin-file
application can still enter human review.

The API rejects the request with `422` when consent is missing or when
`behavioral_signals` contains sensitive keys such as IIN, passport, phone,
address, raw bank-statement, precise-geolocation, or biometric fields. The
consent version is written to the application audit event.

Application Intake v2 also rejects:

- unknown top-level or behavioral fields;
- a requested amount outside `1,000` to `100,000,000`;
- negative, non-finite, fractional count, or over-limit signal values;
- unsupported district, settlement, gender, or employment categories;
- district/settlement mismatches such as `Aksu` with `urban` instead of
  `industrial_city`;
- purpose text longer than 200 characters.

`BehavioralSignalsCreate` is the typed allowlist used by OpenAPI, FastAPI, the
browser form, and the static demo. Missing optional signals remain valid so the
thin-file review path still works; unreviewed proxy fields do not.

Recommended borrower form fields for the first frontend:

- `requested_amount`
- `purpose`
- `district`
- `settlement_type`
- `annual_income`
- `total_outstanding_debt`
- `mobile_banking_logins`
- `online_transfer_frequency`
- `atm_withdrawal_frequency`
- `avg_deposit_amount`
- `debit_card_spending`
- `num_open_loans`
- `late_payment_count`
- `gender`
- `employment_status`

Request example:

```json
{
  "requested_amount": 3000,
  "purpose": "working capital",
  "district": "Pavlodar city",
  "settlement_type": "urban",
  "organization_id": "pavlodar-demo-mfi",
  "consent_confirmed": true,
  "consent_version": "synthetic-demo-v1",
  "behavioral_signals": {
    "annual_income": 52000,
    "total_outstanding_debt": 6500,
    "mobile_banking_logins": 18,
    "online_transfer_frequency": 7,
    "atm_withdrawal_frequency": 2,
    "avg_deposit_amount": 1400,
    "debit_card_spending": 900,
    "num_open_loans": 1,
    "late_payment_count": 0,
    "gender": "Female",
    "employment_status": "Self-employed"
  }
}
```

Response schema:

- `BorrowerApplicationResponse`
- contains lifecycle status, amount, purpose, organization, timestamps, a plain
  status message, and a terminal-state flag
- deliberately excludes behavioral signals, internal score snapshots, analyst
  identity, policy metadata, and analyst notes

Borrower history and detail:

```http
GET /applications
GET /applications/{application_id}
```

Both endpoints require a borrower token and return only applications owned by
that account. The collection is newest-first. Cross-borrower detail access
returns `403`; MFI users use the tenant-scoped `/mfi/applications` contract.

Application timeline:

```http
GET /applications/{application_id}/timeline
```

Response schema:

- `ApplicationTimelineEventResponse`
- chronological events for one application
- currently includes application submission, scoring, and recorded analyst
  decisions when those events exist

Borrowers can only access timelines for their own applications. Their response
removes staff email and internal risk/policy details, retaining only public
lifecycle titles, timestamps, and status changes. MFI/admin users can access the
full timeline for their authorized review queue.

## MFI Analyst Flow

Inspect the deployed scoring model:

```http
GET /mfi/model-status
```

The response states whether scoring is currently allowed and returns the active
model registry record: version, feature schema, training-data label, random
state, validation metrics, recorded limitations, and activation time. This is
decision-support metadata, not evidence that the model is production-ready.

List applications:

```http
GET /mfi/applications
```

Export application portfolio:

```http
GET /mfi/applications/export.csv
```

This returns a CSV file for MFI analyst review. It includes application fields,
model risk fields, recommendation fields, latest analyst decision fields, and
governance flags. It is intended for pilot demos and internal review, not for
sharing real borrower data without consent and privacy controls.

Score an application:

```http
POST /mfi/applications/{application_id}/score
```

Score response includes:

- `high_risk_probability`
- `risk_band`
- `model_version`
- `model_governance`
- `proxy_sensitivity_delta`
- `scenario_scores`
- `decision_support`
- `explanation`
- `top_model_factors`
- `warnings`

`model_governance` is an immutable governance snapshot copied from the active registry
record at scoring time. It includes the feature-schema version, training-data
label, random state, activation time, lifecycle status, and limitations. A
later model activation therefore does not rewrite the provenance of an older
score.

Important current warning: `late_payment_count` is treated as a strong proxy
feature in the synthetic dataset.

Current scoring scenarios:

- `standard`: uses the current research feature set.
- `thin_file_without_late_payment_count`: uses a separately trained model that
  drops `late_payment_count`.

`proxy_sensitivity_delta` is the absolute probability difference between these
two scenarios. A large delta means the score is highly dependent on the
late-payment proxy and should be reviewed carefully.

`decision_support` translates the model output into an analyst-facing
recommendation such as manual review, proxy-sensitive review, or small starter
loan candidate. It is deliberately not an automatic approval or decline: the
MFI analyst still needs to review affordability, context, and policy.

Record an analyst decision:

```http
POST /mfi/applications/{application_id}/decision
```

Request:

```json
{
  "decision": "review",
  "policy_name": "balanced_review",
  "note": "Request income stability evidence."
}
```

Allowed decisions:

- `approve`
- `review`
- `decline`

This endpoint requires the application to be scored first. The response is a
`LoanApplicationResponse` with `decision_result`. This field records the human
analyst decision, not an automatic model decision. Recording a decision also
creates an `application_decision_recorded` audit event.

Lifecycle transitions are enforced as a state machine:

```text
submitted -> scored -> under_review -> approved | declined
                  \-----------------> approved | declined
```

Re-scoring is allowed while an application is `scored` or `under_review`; it
updates the score snapshot without moving an application backward in the
workflow. `approved` and `declined` are terminal. Re-scoring, repeating manual
review, or reversing a terminal decision returns `409` and does not write a new
decision or timeline event.

Open an analyst review packet:

```http
GET /mfi/applications/{application_id}/review-packet
```

Response schema:

- `ApplicationReviewPacketResponse`
- application summary
- model risk summary
- scenario scores and local explanation factors
- latest analyst decision, if recorded
- chronological `decision_history`, including review-to-final transitions
- typed `lifecycle` capabilities: terminal flag, score/rescore action, and
  currently allowed decisions
- `affordability` screening snapshot with submitted income, debt, open-loan
  count, debt/income, requested-amount/income, and completeness
- application timeline events
- governance flags such as proxy-sensitive score, missing model features, or
  `stale_model_version`
- review checklist items for human oversight

Review Readiness / Action Plan v1 is a browser-facing interpretation of the
review packet. It does not add a separate persisted workflow field: the web UI
derives the selected application's score/rescore state, readiness summary,
checklist blockers, allowed decision actions, and terminal locked state from
`lifecycle`, `checklist`, `model_summary`, and `decision_history`. The backend
state machine remains the authority for mutations, and borrower-safe
application responses still exclude this internal review packet.

The review packet is designed as an internal MFI review aid. It summarizes what
the model and analyst workflow currently know, but it is not a legal credit
decision record and does not include validated repayment outcomes.

Affordability ratios use the submitted `annual_income` as their denominator.
They are screening indicators only: the prototype does not know the income
period, loan term, living expenses, verified cash flow, or repayment schedule.
The response therefore carries an explicit interpretation note and must not be
treated as an affordability verdict.

When the stored score version differs from the currently active registry
version, the packet sets `model_summary.is_current_active` to `false`, adds a
`stale_model_version` flag, and requires re-scoring in the human-review
checklist.

`explanation` provides local additive explanation fields for the current
Logistic Regression scoring model:

- `method`
- `baseline_log_odds`
- `total_contribution`
- `predicted_log_odds`
- `high_risk_probability`
- `top_positive_factors`
- `top_protective_factors`
- `top_factors`

Each factor includes `feature`, signed contribution `value`, `abs_value`,
`direction`, and `label`. Positive values raise predicted high-risk log-odds;
negative values lower them. This is not a production governance substitute for
SHAP across all model classes, but it gives the MFI analyst a transparent local
view for the current linear model.

Segment analytics:

```http
GET /mfi/analytics/segments
```

Current segments:

- `settlement_type`
- `pavlodar_district`
- `gender`
- `employment_status`

Policy analytics:

```http
GET /mfi/analytics/policies
```

Response schema:

- `PolicyAnalyticsResponse`
- includes policy-level rows and segment-level rows
- uses scored applications from the local demo database
- reports predicted approve/review/decline trade-offs only

Important limitation: this endpoint does not know real repayment outcomes. It
uses predicted high-risk probabilities from scored applications, so it should be
read as a live portfolio preview, not as validated profit or default evidence.

Monte Carlo portfolio simulation:

```http
POST /mfi/simulations/portfolio
```

Request example:

```json
{
  "iterations": 5000,
  "seed": 20260619,
  "policy": "balanced_review",
  "scenarios": ["baseline", "adverse", "severe"],
  "review_approval_rate": 0.50,
  "interest_margin_rate": 0.22,
  "loss_given_default": 0.65,
  "operating_cost_per_approved": 0,
  "macro_volatility": 0.25,
  "calibration_volatility": 0.15
}
```

The endpoint runs 100 to 20,000 seeded iterations over the caller's
organization-scoped scored portfolio. It returns paired baseline/adverse/severe
distributions for:

- approved count and exposure;
- default count and default rate;
- one-period portfolio result and result per approved loan;
- mean stressed probability;
- probability of a negative result;
- 5th, 50th, and 95th percentiles;
- Monte Carlo standard errors for mean result, mean defaults, and loss
  probability.

The synchronous prototype caps work at 20 million borrower-iterations
(`scored_application_count * iterations`). Larger runs return `409` and should
eventually move to a background worker.

One macro shock is shared across the portfolio in each iteration, while an
application-level calibration shock captures residual probability uncertainty.
Manual-review applications enter the book at the supplied review approval
rate. Common random numbers are reused across scenarios so stress comparisons
are less noisy and preserve the same underlying draws.

Runs are reproducible for the same portfolio, score snapshots, seed, policy,
and assumptions. Every successful call records a `portfolio_simulation_run`
audit event with inputs and compact scenario summaries. Unscored applications
are reported but excluded; a portfolio with no scored applications returns
`409`.

The response includes a SHA-256 `portfolio_fingerprint` over the canonical
scored snapshot and stores the request plus full response in the immutable local
simulation registry. Successful runs can be listed and reopened through:

```http
GET /mfi/simulations
GET /mfi/simulations/{simulation_id}
```

The list endpoint returns compact `PortfolioSimulationSummary` records with
typed `PortfolioSimulationScenarioSummary` rows. The
detail endpoint returns the original `PortfolioSimulationResponse`, including
assumptions, fingerprint, warnings, distributions, and diagnostics. Analyst
access is organization-scoped; admins can inspect all runs. Missing IDs return
`404`, and cross-tenant detail access returns `403`.

The response warns when unscored applications were excluded, score snapshots
mix multiple model versions, or a stored score is not from the active model.
These conditions do not silently disappear inside portfolio aggregation.
The default operating cost is zero and produces its own warning; enter a cost
in the same amount units as the portfolio before interpreting financial output.

This is scenario planning, not borrower scoring, a repayment forecast,
regulatory VaR, or an automatic lending rule. The full formula and
interpretation boundary are documented in
`docs/MONTE_CARLO_METHODOLOGY.md`.

Decision analytics:

```http
GET /mfi/analytics/decisions
```

Response schema:

- `DecisionAnalyticsResponse`
- summarizes latest human MFI decisions per application
- reports approve/review/decline counts and rates
- reports policy/decision combinations when a policy name was recorded
- reports decision mix by model risk band, Pavlodar district, recommendation,
  and proxy-sensitivity bucket

This endpoint is about analyst workflow, not model performance. It helps show
how human decisions compare with model risk, regional context, proxy warnings,
and model review recommendations. It still does not know whether a loan was
repaid, so it must not be read as validated credit-performance evidence.

## Admin Flow

List registered model versions:

```http
GET /admin/model-versions
```

Register a candidate configuration:

```http
POST /admin/model-versions
```

```json
{
  "version": "research-v0.2",
  "model_name": "Logistic Regression",
  "feature_schema_version": "behavioral-v2",
  "training_data_label": "synthetic-credit-risk-v2",
  "random_state": 77,
  "metrics": {"roc_auc": 0.82, "brier_score": 0.18},
  "limitations": [
    "Synthetic validation only.",
    "Human review is required."
  ]
}
```

Activate a registered version:

```http
POST /admin/model-versions/{version}/activate
```

Activation is atomic: the previous active version becomes `inactive` and the
target becomes the only active runtime. Registration and activation create
`model_version_registered` and `model_version_activated` audit events. In this
prototype each registered Logistic Regression version is trained
deterministically from its stored random state; production deployment should
replace this with signed, immutable model artifacts.

Audit events:

```http
GET /admin/audit-events
```

Clear local demo applications:

```http
DELETE /admin/applications
```

This keeps users and records an `applications_cleared` audit event.

Current audited actions:

- `user_registered`
- `application_created`
- `application_scored`
- `application_decision_recorded`
- `model_version_registered`
- `model_version_activated`
- `portfolio_simulation_run`
- `staff_user_created`
- `staff_mfa_attested`
- `staff_mfa_login_verified`
- `staff_mfa_challenge_failed`
- `staff_session_revoked`
- `staff_user_disabled`
- `staff_user_reactivated`
- `staff_invite_created`
- `staff_invite_delivery_attempted`
- `staff_invite_delivered`
- `staff_invite_rotated`
- `staff_invite_accepted`
- `staff_invite_revoked`
- `organization_created`
- `user_logged_out`
- `applications_cleared`

## Persistence

Default local database:

```text
data/app/microscore.sqlite3
```

Override with:

```powershell
$env:MICROSCORE_API_DB_PATH = "C:\path\to\microscore.sqlite3"
```

The active storage backend is explicit and validated at startup:

```powershell
$env:MICROSCORE_STORAGE_BACKEND = "sqlite"
```

`sqlite` is the only implemented runtime backend in PostgreSQL Readiness v1.
Configuring `postgres` or `postgresql` is rejected rather than silently running
against an incomplete persistence layer. `GET /health` returns a typed
`storage` readiness block with the active backend, database path, required
tables, JSON text columns, tenant-scoped columns, capability statuses, and the
PostgreSQL migration checklist. This is migration metadata only; it does not
require or connect to a live PostgreSQL server.

Runtime database files are intentionally ignored by Git.
The SQLite schema persists organizations, users, staff invites, expiring
sessions, applications, analyst decisions, audit events, and `model_versions`.
Existing development databases receive these tables through idempotent startup
migrations and are seeded with `research-v0.1` as the initial active version.

## Prototype Data Scale

The current model is trained on synthetic data. Demo numeric values use the
same prototype scale as that synthetic dataset. Real KZT-denominated borrower
data will need a separate calibration step before the model can be interpreted
as a realistic lending tool.

The monetary boundary is defined in
`docs/KZT_CALIBRATION_ASSUMPTIONS.md`: `requested_amount`, affordability
inputs, Monte Carlo exposure, and portfolio result are prototype amount units
until local KZT principal, income, debt, tenor, margin, LGD, operating cost, and
repayment outcomes are documented and validated.
