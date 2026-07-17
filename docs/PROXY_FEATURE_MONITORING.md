# Proxy Feature Monitoring v2

This document defines the Analytics/ML guardrail for tracking proxy-feature
risk in MicroScore research artifacts. It does not change product API behavior,
scoring thresholds, borrower lifecycle, or analyst decision rules.

## Purpose

MicroScore currently uses synthetic borrower-level data. The strongest known
finding is that `late_payment_count` behaves like a dominant repayment-history
proxy: it can make model metrics look strong while weakening the thin-file
claim.

Proxy Monitoring v2 makes that limitation visible in every research-report run.
It expands monitoring from one feature to related proxy families:

| Family | Example features | Risk |
| --- | --- | --- |
| Repayment history | `late_payment_count` | Can recreate traditional credit-history exclusion. |
| Debt/formal credit | `num_open_loans`, `total_outstanding_debt` | May proxy prior access to credit rather than independent behavior. |
| Prototype monetary scale | `annual_income`, `loan_application_amount`, `avg_monthly_balance` | Not calibrated KZT; may proxy wealth or formal-account access. |
| Derived affordability | `loan_to_income_ratio`, `income_to_debt_ratio`, `total_credit_pressure`, `debt_per_open_loan` | Depends on unvalidated amount units and missing tenor/cash-flow context. |
| Digital access | `mobile_banking_logins`, `online_transfer_frequency`, `atm_withdrawal_frequency`, `digital_activity_score` | May proxy internet, smartphone, cash, branch, or rural access. |

## Generated Artifact

The research report command writes:

```powershell
.venv\Scripts\python -m microscore --reports
```

Output:

```text
reports/research-artifacts/proxy_monitoring.csv
```

The table reports:

- `feature`
- `feature_family`
- `single_feature_roc_auc`
- `directional_roc_auc`
- `risk_rate_spread`
- `risk_direction`
- `proxy_strength`
- `monitoring_action`
- `rationale`

`directional_roc_auc` treats a feature as important whether high values or low
values correlate with high risk. This prevents inverse proxies from being
mistaken for weak signals.

## Interpretation

Proxy strength is a research warning, not a product decision.

- `high`: must be reviewed before real-data, KZT, thin-file, fairness, or pilot
  claims.
- `moderate`: keep in artifacts and segment review.
- `low`: monitor for drift and future data changes.

A high-strength proxy does not automatically remove a feature from the
prototype model. It means the claim around that feature must stay careful until
validated with consented local data, segment analysis, and analyst review.

## Connection To KZT Calibration

KZT calibration cannot be separated from proxy monitoring. Monetary values and
affordability ratios can become socioeconomic proxies when they are unverified,
uncalibrated, or missing tenor and repayment-schedule context.

Before making KZT-denominated claims, MicroScore needs:

- real KZT principal, income, debt, tenor, fee, and repayment fields;
- documented margin, LGD, operating cost, and review-conversion assumptions;
- held-out calibration on local repayment outcomes;
- segment-level error analysis;
- proxy-monitoring review for repayment-history, monetary-scale,
  affordability, and digital-access features.

## Product Boundary

This monitor must not:

- create automatic approve or decline behavior;
- change Review Readiness semantics;
- change API response shapes;
- change policy thresholds;
- replace human analyst judgment;
- turn prototype amount units into calibrated KZT.

It is a research artifact that keeps model limitations visible while the
product remains decision-support only.
