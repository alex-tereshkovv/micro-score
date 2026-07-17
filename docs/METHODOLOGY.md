# MicroScore Methodology

MicroScore is a research prototype for behavioral credit-risk scoring in
Pavlodar region, Kazakhstan. The goal is not to automate lending decisions, but
to study whether digital and financial behavior can improve credit access for
borrowers with thin or missing formal credit histories.

## Research Question

Can behavioral financial signals help microfinance organizations identify
responsible borrowers who may be rejected by traditional credit systems?

The project studies three connected questions:

- Predictive validity: can behavioral signals estimate credit risk?
- Robustness: does the model rely on leakage or overly strong proxy variables?
- Inclusion: how do model thresholds affect access for rural and underserved
  borrowers?

## Current Data Status

The current borrower-level dataset is synthetic. It is useful for pipeline
development, leakage checks, experiment design, and product prototyping, but it
is not evidence that the model is ready for real lending.

The regional context layer uses a separate public-reference table in
`data/external/pavlodar_district_profiles.csv`.

Evidence-based regional fields:

- district/city names
- settlement type
- 2023 population estimates
- population-based sampling weights

Model-assumption regional fields:

- distance to Pavlodar
- digital access index
- income index
- MFI branch access index
- seasonal income risk
- financial access gap

## Feature Groups

Core behavioral and financial features include:

- mobile banking logins
- transfer frequency
- ATM withdrawal frequency
- deposit behavior
- debit-card spending
- account age
- debt burden
- loan amount relative to income

Engineered features include:

- `income_to_debt_ratio`
- `digital_activity_score`
- `deposit_to_spending_ratio`
- `loan_to_income_ratio`
- `total_credit_pressure`
- `debt_per_open_loan`

## Leakage Policy

The default model drops variables that are unrealistic for a behavioral-scoring
experiment or too close to the outcome:

- `customer_id`
- `credit_score`
- `loan_default_history`
- `fraud_flag`

The project also audits `late_payment_count`. It is not dropped by default, but
it is treated as a sensitive proxy because it currently dominates feature
importance. In the synthetic dataset, removing it drops ROC-AUC to roughly
random performance. That makes it a central modeling and ethics question, not
just a useful predictor.

Proxy Monitoring v2 extends this into a multi-feature research guardrail. The
reports workflow now scans repayment-history, debt/formal-credit,
monetary-scale, derived affordability, and digital-access features for
single-feature dominance. It writes `proxy_monitoring.csv` and keeps the result
in the generated report summary. This is not a product decision rule; it is a
research artifact that prevents thin-file, KZT, fairness, or pilot claims from
quietly depending on one proxy-heavy feature family.

## Models

The current baseline models are:

- Logistic Regression
- Random Forest

The pipeline uses:

- sklearn `Pipeline`
- one-hot encoding
- median/mode imputation
- scaling for numeric fields
- stratified train/test split
- 5-fold cross-validation

This structure prevents preprocessing leakage by fitting transformations only
inside training folds.

## Evaluation Metrics

Standard model metrics:

- ROC-AUC
- Brier score
- accuracy
- precision
- recall
- F1
- confusion matrix

Decision metrics:

- approval rate
- default rate among approved borrowers
- good-borrower rejection rate
- bad-borrower approval rate
- expected profit/loss under lending assumptions
- segment approval rate

The project intentionally treats ROC-AUC as necessary but insufficient. A credit
model must also be evaluated as a decision system with threshold, access, and
loss trade-offs.

## Error Analysis

The project now reports false-positive and false-negative behavior on the
held-out test set:

```powershell
.venv\Scripts\python -m microscore --error-analysis
```

In credit-risk terms:

- false positives are good borrowers who may be wrongly flagged as high risk;
- false negatives are high-risk borrowers who may be missed by the model.

The reports workflow saves:

- `error_analysis_summary.csv`;
- `segment_error_analysis.csv`;
- `false_positive_examples.csv`;
- `false_negative_examples.csv`;
- `prediction_errors.csv`.

Current synthetic-data finding: many confident false negatives have
`late_payment_count = 0`. This reinforces the proxy-risk concern: when repayment
history is absent or weak, the current synthetic dataset does not provide enough
independent behavioral signal.

## Threshold Policy Analysis

The project now compares three-zone decision policies:

```powershell
.venv\Scripts\python -m microscore --policy-analysis
```

Each policy has:

- an auto-approval zone for low predicted risk;
- a manual-review zone for uncertain applications;
- an auto-decline zone for very high predicted risk.

Current synthetic-data policies include:

- `lender_protective`;
- `balanced_review`;
- `inclusion_first`;
- `starter_loan_review`.

The goal is not to recommend an operational lending policy. The goal is to make
the access-vs-risk trade-off explicit: increasing auto-approval also increases
the rate at which high-risk borrowers are approved, while strict decline
policies can wrongly reject good borrowers.

## Ablation Study

The project now runs a feature-group ablation study with:

- raw all-feature diagnostic ceiling;
- no-leakage baseline;
- no `late_payment_count` thin-file stress test;
- behavioral-only features;
- regional-only features;
- behavioral plus regional features.

The ablation includes a Dummy Classifier baseline, ROC-AUC, Brier score, and
metric deltas against the no-leakage baseline. This makes it clear whether a
new feature group adds real signal or only makes the model look stronger
because of proxy or leakage effects.

Current synthetic-data result: removing `late_payment_count` drops the model to
near-random ROC-AUC, while behavioral-plus-regional features remain weak. This
does not disprove the project idea; it shows that the current synthetic dataset
is not enough to validate thin-file behavioral scoring.

The API prototype also reports an application-level proxy-sensitivity check:
the standard score is compared with a separately trained thin-file model that
drops `late_payment_count`. This helps identify cases where the model's risk
estimate depends heavily on the strongest repayment-history proxy.

The API adds a decision-support layer on top of the model output. It converts
standard and thin-file scores into a human-review recommendation with rationale
and next steps. This is intentionally framed as analyst support, not automated
lending approval.

## Monte Carlo Portfolio Uncertainty

The Policy Lab now complements deterministic threshold tables with a seeded
Monte Carlo portfolio simulation. This layer does not alter an individual
borrower's probability. It applies the selected policy to stored score
snapshots, then simulates manual-review conversion, correlated macro movement,
application-level calibration uncertainty, and Bernoulli defaults.

Baseline, adverse, and severe scenarios share the same underlying random draws.
This common-random-number design makes differences between scenarios reflect
the stress assumption rather than unrelated simulation noise. Results report
means and 5th/50th/95th percentiles for approvals, defaults, exposure, and a
simple one-period financial result, plus the probability of a negative result.

The formula, defaults, reproducibility rules, and interpretation limits are in
[MONTE_CARLO_METHODOLOGY.md](MONTE_CARLO_METHODOLOGY.md). Because current risk
probabilities are synthetic and not calibrated on MFI outcomes, simulation
ranges are scenario-planning diagnostics only. They are not forecasts,
regulatory VaR, capital requirements, pricing guidance, or evidence that a
policy is safe.

Monetary outputs use prototype amount units, not calibrated KZT. The
pre-pilot boundary for requested amounts, margin, LGD, operating cost, policy
thresholds, and evidence required before KZT-denominated claims is defined in
[KZT_CALIBRATION_ASSUMPTIONS.md](KZT_CALIBRATION_ASSUMPTIONS.md).

## Local Explanations

The API now returns individual local explanations for the current Logistic
Regression scoring model. The explanation is additive in log-odds space:

```text
baseline_log_odds + total_feature_contribution = predicted_log_odds
```

Positive factor values increase predicted high-risk probability. Negative
factor values reduce it. The API and frontend separate these into:

- top positive factors;
- top protective factors;
- top factors by absolute contribution.

This is a transparent explanation method for the current linear model. It is
not a claim that future nonlinear models are already explainable. If the project
adds Random Forest, XGBoost, or LightGBM scoring to the API, it should add SHAP
or TreeSHAP explanations and validate them separately.

## Research Artifacts

The project can save reproducible research outputs with:

```powershell
.venv\Scripts\python -m microscore --reports
```

The generated `reports/research-artifacts/` folder includes:

- model metrics;
- feature-group ablation results;
- proxy monitoring results;
- calibration bins;
- false-positive and false-negative analysis;
- threshold policy analysis;
- calibration and ablation plots;
- one example local explanation summary;
- top explanation factors.

This keeps notebook output from becoming the only source of truth and makes the
research easier to review from GitHub.

## Fairness And Segment Audits

The current audit layer reports metrics by:

- gender
- employment status
- Pavlodar district
- settlement type

The goal is not to use protected or sensitive features blindly in decisions.
The goal is to measure whether model behavior differs across groups and whether
threshold choices unintentionally reduce access for underserved borrowers.

Proxy monitoring is paired with these segment audits. A feature can be
predictive and still unacceptable for real lending if it mainly reflects
repayment-history exclusion, uncalibrated KZT scale, affordability assumptions,
or digital-access gaps. Any high-strength proxy must be reviewed before the
project makes real-data, KZT-denominated, or operational-readiness claims.

## Regional Methodology

The Pavlodar regional layer is a transparent scaffold for local analysis. It is
not real MFI client data. It lets the project test questions that will matter in
a future local pilot:

- Do rural borrowers receive systematically lower approval rates?
- Does distance from Pavlodar correlate with lower financial access?
- Do industrial cities and rural districts show different risk/access patterns?
- How would a threshold optimized for profit affect inclusion in remote areas?

When real partner data becomes available, simulated regional assumptions should
be replaced with observed borrower location, income stability, financial-access
and repayment-performance data.

## Current Limitations

- Borrower-level data is synthetic.
- Regional access indices are assumptions, not measured local facts.
- The target variable is simplified as binary `credit_risk`.
- The model is not calibrated for real loan pricing.
- The project does not yet include temporal repayment behavior.
- The project is not yet a deployed application with secure user accounts.

## Next Methodological Steps

1. Add SHAP or TreeSHAP explanations for future nonlinear/tree models.
2. Track generated report artifacts over model versions.
3. Expand the no-repayment-history scenario with calibration and stability
   checks.
4. Add false-positive and false-negative case review artifacts.
5. Add temporal features once longitudinal data exists.
6. Replace regional assumptions with official open data where possible.
7. Validate KZT calibration assumptions with consented local MFI data.
8. Seek anonymized pilot data from a local MFI.
