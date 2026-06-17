# Pilot Data Schema

This document defines the minimum data MicroScore should request during a
future supervised pilot with a microfinance organization. The goal is to test
credit-risk decision support without collecting unnecessary sensitive data.

The current project is not running a real pilot. This schema is a planning
artifact for future validation.

The API exposes the same boundary as a read-only contract at:
`GET /governance/pilot-readiness`.

## Design Principles

- Collect only what is needed for risk research and analyst review.
- Keep personal identifiers separate from model features.
- Require borrower consent before any behavioral or financial signal is used.
- Avoid raw bank statements in the early pilot; start with summarized fields.
- Keep every model score tied to a model version and feature schema.
- Make every analyst action auditable.

## Data Classes

| Data class | Collect in pilot? | Use in model? | Notes |
| --- | --- | --- | --- |
| Internal borrower id | Yes | No | Random pilot id, not an IIN. |
| Name | Avoid if possible | No | MFI may need it operationally; MicroScore does not. |
| IIN/passport number | No | No | Too sensitive for this prototype stage. |
| Phone/email | Avoid if possible | No | Use only if the MFI already manages contact. |
| District/settlement type | Yes | Yes, with caution | Needed to validate Pavlodar regional assumptions. |
| Income band | Yes | Yes | Prefer bands over exact income in first pilot. |
| Debt band | Yes | Yes | Prefer summarized debt burden. |
| Open loan count | Yes | Yes | Useful risk signal, but verify source quality. |
| Late payment count | Yes | Yes, flagged | Strong proxy feature; must be audited separately. |
| Mobile banking activity | Yes | Yes | Use counts or ranges, not raw transaction logs. |
| Transaction frequency | Yes | Yes | Summarized monthly count only. |
| Deposit/spending bands | Yes | Yes | Use ranges to reduce privacy exposure. |
| Gender | Optional | Audit only | Fairness audit, not model input by default. |
| Employment type | Yes | Model/audit | Important for segment review and stability checks. |
| Region beyond Pavlodar | Later | Audit/model later | Add only when pilot expands beyond one region. |

## Proposed Tables

### `pilot_borrowers`

| Field | Type | Model input? | Notes |
| --- | --- | --- | --- |
| `borrower_id` | string | No | Random internal id. |
| `consent_version` | string | No | Version of consent text accepted. |
| `created_at` | datetime | No | Pilot audit field. |
| `district` | string | Yes | Pavlodar district or city. |
| `settlement_type` | string | Yes | Urban, rural, industrial city, etc. |
| `gender` | string/null | No | Use for fairness audit only. |
| `employment_type` | string | Yes | Formal, informal, self-employed, unemployed, etc. |

### `pilot_applications`

| Field | Type | Model input? | Notes |
| --- | --- | --- | --- |
| `application_id` | string | No | Random application id. |
| `borrower_id` | string | No | Links to borrower table. |
| `requested_amount_band` | string | Yes | Band instead of exact amount for early pilot. |
| `loan_purpose` | string | Yes | Business, household, emergency, education, etc. |
| `income_band` | string | Yes | Monthly or annual band, depending on partner data. |
| `debt_band` | string | Yes | Summarized outstanding obligations. |
| `open_loan_count` | integer | Yes | Count only. |
| `late_payment_count_12m` | integer | Yes, flagged | Must be proxy-audited in every report. |
| `submitted_at` | datetime | No | Application timeline. |

### `pilot_behavioral_signals`

| Field | Type | Model input? | Notes |
| --- | --- | --- | --- |
| `application_id` | string | No | Links to application. |
| `mobile_login_band_30d` | string | Yes | Example: none, low, medium, high. |
| `online_transfer_band_30d` | string | Yes | Band or count range. |
| `transaction_frequency_band_30d` | string | Yes | Avoid raw merchant-level logs. |
| `deposit_band_90d` | string | Yes | Summarized deposit behavior. |
| `card_spending_band_90d` | string | Yes | Summarized spending behavior. |
| `data_source_quality` | string | Audit | Self-reported, MFI system, verified, unknown. |

### `pilot_score_results`

| Field | Type | Model input? | Notes |
| --- | --- | --- | --- |
| `score_id` | string | No | Unique score result id. |
| `application_id` | string | No | Links to application. |
| `model_version` | string | No | Required for reproducibility. |
| `feature_schema_version` | string | No | Prevents silent feature drift. |
| `risk_probability` | float | No | Calibrated probability if validated. |
| `risk_band` | string | No | Low, medium, high, or review. |
| `top_factors_json` | json | No | Explanation shown to analyst. |
| `proxy_warnings_json` | json | No | Example: late-payment dominance warning. |
| `created_at` | datetime | No | Audit field. |

### `pilot_analyst_actions`

| Field | Type | Model input? | Notes |
| --- | --- | --- | --- |
| `action_id` | string | No | Unique audit event id. |
| `application_id` | string | No | Links to application. |
| `analyst_id` | string | No | MFI-side role id, not public. |
| `action_type` | string | No | Viewed, requested_more_info, approved, declined, etc. |
| `reason_code` | string/null | No | Structured reason for review. |
| `created_at` | datetime | No | Audit timestamp. |

## Explicitly Out Of Scope

Do not collect these in the current prototype or early public demo:

- IINs, passport numbers, or national ID images;
- raw bank statements;
- raw card transaction descriptions;
- precise geolocation;
- social media contacts or phone-book data;
- device fingerprinting;
- photos, biometric data, or voice recordings.

## Validation Questions

Before any real pilot, MicroScore needs answers to these questions:

1. Which fields can an MFI provide legally and ethically?
2. Which fields are already available in summarized form?
3. Which fields require explicit borrower consent?
4. Which features are stable across Pavlodar city, towns, and rural districts?
5. Does `late_payment_count` remain a dominant proxy on real data?
6. Which segments show systematically higher false positive or false negative
   rates?

## First Pilot Success Criteria

A first pilot should be considered successful only if it can show:

- consented, minimal, non-invasive data collection;
- no use of direct identity fields as model features;
- reproducible model versioning;
- calibrated probability review, not just ROC-AUC;
- segment/fairness reporting by gender, employment type, and district;
- analyst feedback on whether explanations are understandable;
- documented reasons for false positives and false negatives.

This is the quiet plumbing that makes a future MicroScore pilot serious. It is
less flashy than a new chart, but it prevents the project from growing in a
messy direction later.
