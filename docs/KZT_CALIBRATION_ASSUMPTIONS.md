# KZT Calibration Assumptions Pack

This pack defines how MicroScore should talk about monetary values before the
project has real, consented Kazakhstan MFI repayment data.

It is a research and validation contract, not a product-behavior change.

## Current Position

MicroScore currently uses **prototype amount units**. The synthetic demo
contains fields such as `requested_amount`, `annual_income`,
`total_outstanding_debt`, approved exposure, and portfolio result, but those
values are on the same artificial scale as the synthetic dataset.

They must not be described as calibrated KZT.

This means:

- `requested_amount` is a synthetic principal-like amount used for scoring,
  policy tables, and scenario planning;
- `annual_income` and `total_outstanding_debt` are synthetic affordability
  inputs in the same prototype scale;
- Monte Carlo `approved_exposure`, `portfolio_result`, and
  `result_per_approved` are output amount units, not KZT forecasts;
- a formatting helper or demo label must not be treated as evidence of
  currency calibration.

## Requested Amount Interpretation

Before calibration, `requested_amount` means:

```text
prototype loan amount used for relative scoring, affordability ratios,
policy comparison, and portfolio scenario planning
```

It does not yet encode:

- actual KZT principal;
- loan tenor;
- repayment schedule;
- fees;
- collateral;
- collections timing;
- refinance or rollover behavior.

Future KZT use must either ingest true KZT values under a documented data-use
agreement or explicitly transform local values into a modeling scale with a
recorded transformation. A fixed synthetic-to-KZT conversion factor is not
allowed.

## Policy Threshold Interpretation

Policy thresholds operate on model high-risk probabilities. Until the model is
validated on local repayment outcomes, these are prototype risk scores.

Terms such as `auto-approval`, `manual review`, and `auto-decline` in research
tables mean **simulated threshold-policy actions**. They are not instructions
to automatically approve or decline a real borrower.

Every operational workflow must still require a human analyst decision and
borrower-safe communication.

Policy thresholds must not be tuned against prototype monetary output alone.
Before operational use, threshold candidates need separate review of:

- calibrated default probabilities;
- segment-level false-positive and false-negative rates;
- proxy sensitivity, especially `late_payment_count`;
- analyst override and appeal outcomes;
- KZT exposure and affordability under real tenor and repayment schedules.

## Monte Carlo Assumption Defaults

The current Monte Carlo defaults are explicit prototype assumptions:

| Field | Default | Meaning before calibration |
| --- | ---: | --- |
| `review_approval_rate` | `0.50` | Assumed share of manual-review cases that enter the simulated book. |
| `interest_margin_rate` | `0.22` | One-period margin applied to prototype amount units. |
| `loss_given_default` | `0.65` | Assumed loss share if a simulated approved loan defaults. |
| `operating_cost_per_approved` | `0.0` | Placeholder because the demo has no validated per-loan cost scale. |
| `macro_volatility` | `0.25` | Transparent portfolio-level stress noise, not a fitted macro model. |
| `calibration_volatility` | `0.15` | Prototype uncertainty around unvalidated risk probabilities. |

These defaults can support demo and methodology review. They cannot support
pricing, capital, profitability, or deployment claims.

When these assumptions appear in a chart, table, CSV export, or demo script,
the surrounding label should say **prototype amount units** or **scenario
assumptions**. It should not say expected KZT profit, expected KZT loss, KZT
VaR, regulatory capital, portfolio yield, or repayment forecast.

## Proxy Monitoring Connection

KZT calibration and proxy monitoring are linked. Monetary fields and derived
ratios can behave like socioeconomic proxies if they mainly identify wealth,
formal-account access, or prior access to credit rather than independent
repayment behavior.

Proxy Monitoring v2 therefore tracks these families together:

- repayment-history proxy: `late_payment_count`;
- formal-credit/debt proxies: `num_open_loans`, `total_outstanding_debt`;
- prototype monetary-scale proxies: `annual_income`,
  `loan_application_amount`, `avg_monthly_balance`;
- derived affordability proxies: `loan_to_income_ratio`,
  `income_to_debt_ratio`, `total_credit_pressure`, `debt_per_open_loan`;
- digital-access proxies: `mobile_banking_logins`,
  `online_transfer_frequency`, `atm_withdrawal_frequency`,
  `digital_activity_score`.

Any high-strength proxy in generated reports is a research warning. It does not
automatically remove the feature, approve a borrower, decline a borrower, or
change product behavior. It does require documented review before KZT,
thin-file, fairness, or pilot-readiness claims.

## Evidence Required Before KZT-Denominated Claims

MicroScore can start making KZT-denominated claims only after the project has:

1. consented local application and repayment outcomes;
2. verified KZT principal, income, debt, tenor, fee, and repayment fields;
3. observed or documented interest margin, funding cost, LGD, operating cost,
   collections timing, and review-conversion assumptions;
4. model calibration on held-out local outcomes;
5. segment and proxy audits, including `late_payment_count` sensitivity;
6. validation of policy-threshold behavior against human decisions and
   repayment outcomes;
7. written approval that outputs are suitable for the intended pilot scope.

Until then, use phrases such as:

- prototype amount units;
- synthetic/demo scale;
- scenario-planning diagnostics;
- threshold-policy simulation;
- not calibrated KZT;
- not a forecast or legal credit decision.

Avoid phrases such as:

- expected KZT profit;
- validated KZT loss;
- real portfolio forecast;
- automatic approval policy;
- production pricing guidance.

Also avoid:

- calibrated affordability verdict;
- KZT repayment forecast;
- regulatory capital estimate;
- guaranteed portfolio sustainability;
- validated inclusion impact.

## First-Pass Research Deliverables

A first-pass KZT assumptions pack is complete only when it has:

1. a written boundary between prototype amount units and real KZT;
2. a list of monetary fields and whether each is observed, synthetic, derived,
   or pending validation;
3. a table of Monte Carlo assumptions with source status and evidence needed;
4. proxy monitoring artifacts for repayment-history, monetary-scale,
   affordability, and digital-access signals;
5. tests that prevent docs from dropping the synthetic/prototype warning;
6. no product API, scoring, lifecycle, or frontend behavior changes.

## Product Boundary

This pack does not change the API, model, or frontend behavior. It only defines
the language and evidence boundary for interpreting existing outputs.

Product surfaces may show amount-unit scenario ranges for demonstration, but
they should keep synthetic-data, human-review, and not-a-forecast warnings near
Monte Carlo, Policy Lab, and Review Readiness views.
