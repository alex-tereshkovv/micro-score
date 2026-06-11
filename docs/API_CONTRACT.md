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

## Roles

- `borrower`: can create and view own loan applications.
- `mfi_analyst`: can view all applications, score applications, and view
  segment and policy analytics.
- `admin`: can do MFI analyst actions and view audit events.

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

## Borrower Application Form

Endpoint:

```http
POST /applications
```

Required fields:

- `requested_amount`
- `behavioral_signals`

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

- `LoanApplicationResponse`
- includes `score_result: null` until an MFI analyst scores the application

## MFI Analyst Flow

List applications:

```http
GET /mfi/applications
```

Score an application:

```http
POST /mfi/applications/{application_id}/score
```

Score response includes:

- `high_risk_probability`
- `risk_band`
- `model_version`
- `proxy_sensitivity_delta`
- `scenario_scores`
- `decision_support`
- `explanation`
- `top_model_factors`
- `warnings`

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

## Prototype Data Scale

The current model is trained on synthetic data. Demo numeric values use the
same prototype scale as that synthetic dataset. Real KZT-denominated borrower
data will need a separate calibration step before the model can be interpreted
as a realistic lending tool.
