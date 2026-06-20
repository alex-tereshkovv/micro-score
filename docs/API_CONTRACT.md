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
  "role": "borrower"
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
for a production identity provider, MFA, HTTPS, distributed rate limiting, or
a formal security review.

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

The temporary-password flow is suitable only for the prototype. A production
version should use expiring invitation links, forced password setup, MFA, and
MFI organization membership.

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
- `behavioral_signals`

The API rejects the request with `422` when consent is missing or when
`behavioral_signals` contains sensitive keys such as IIN, passport, phone,
address, raw bank-statement, precise-geolocation, or biometric fields. The
consent version is written to the application audit event.

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
- application timeline events
- governance flags such as proxy-sensitive score, missing model features, or
  `stale_model_version`
- review checklist items for human oversight

The review packet is designed as an internal MFI review aid. It summarizes what
the model and analyst workflow currently know, but it is not a legal credit
decision record and does not include validated repayment outcomes.

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

Runtime database files are intentionally ignored by Git.
The SQLite schema persists organizations, users, expiring sessions,
applications, analyst decisions, audit events, and `model_versions`. Existing
development databases receive the model registry through an idempotent startup
migration and are seeded with `research-v0.1` as the initial active version.

## Prototype Data Scale

The current model is trained on synthetic data. Demo numeric values use the
same prototype scale as that synthetic dataset. Real KZT-denominated borrower
data will need a separate calibration step before the model can be interpreted
as a realistic lending tool.
