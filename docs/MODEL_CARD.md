# MicroScore Model Card

## Model Name

MicroScore research baseline, version `research-v0.1`.

## Summary

MicroScore is an interpretable alternative credit-risk scoring prototype for
thin-file borrowers in Pavlodar, Kazakhstan. It compares standard behavioral
credit-risk models with a thin-file scenario that removes the strongest
repayment-history proxy, `late_payment_count`.

## Intended Use

- Research prototype for studying behavioral credit-risk scoring.
- Educational and portfolio demonstration of responsible ML for lending.
- Internal decision-support prototype for MFI analysts.
- Tool for exploring proxy risk, threshold trade-offs, and segment audits.

## Not Intended Use

- Automatic loan approval or rejection.
- Real lending decisions without validated local data.
- Use as a credit bureau replacement.
- Use on real borrowers without consent, privacy review, and model validation.
- Use in production without calibration, monitoring, security, and governance.

## Model Types

Current baseline models:

- Logistic Regression
- Random Forest

API scoring currently uses Logistic Regression because it is easier to explain
and audit in the prototype.

## Dataset

The borrower-level dataset is synthetic. It contains behavioral and financial
features such as income, debt, deposits, card spending, digital activity, open
loans, and late-payment count.

The Pavlodar regional layer is a transparent scaffold. Some fields are based on
public context; others are hypotheses that require validation.

The separate public benchmark uses UCI Default of Credit Card Clients. That
dataset is real public credit-card default data from Taiwan, not Pavlodar
microfinance data.

See [DATA_STATEMENT.md](DATA_STATEMENT.md).

## Current Metrics

Current synthetic-data baseline:

| Scenario | Model | ROC-AUC | Notes |
| --- | --- | ---: | --- |
| Full feature set | Logistic Regression | 0.806 | Includes `late_payment_count`. |
| Full feature set | Random Forest | 0.830 | Includes `late_payment_count`. |
| Without `late_payment_count` | Logistic Regression | 0.486 | Near-random ranking in the synthetic data. |
| Without `late_payment_count` | Random Forest | 0.492 | Near-random ranking in the synthetic data. |

Current proxy audit:

- `late_payment_count` single-feature ROC-AUC is about `0.827`.
- For `late_payment_count >= 4`, the synthetic dataset shows a high-risk rate
  of `1.0`, which is unrealistically sharp.
- Proxy Monitoring v2 now also tracks adjacent monetary-scale,
  affordability, debt/formal-credit, and digital-access proxies in
  `reports/research-artifacts/proxy_monitoring.csv`.

Current ablation study:

| Scenario | Logistic Regression ROC-AUC | Random Forest ROC-AUC | Notes |
| --- | ---: | ---: | --- |
| Raw all features | 0.966 | 1.000 | Diagnostic ceiling; includes leakage-like fields. |
| No leakage baseline | 0.806 | 0.830 | Default research baseline. |
| No `late_payment_count` | 0.486 | 0.492 | Thin-file stress test. |
| Behavioral only | 0.499 | 0.494 | Weak signal in the current synthetic data. |
| Regional only | 0.551 | 0.551 | Simulated regional context only. |
| Behavioral + regional | 0.547 | 0.529 | Does not yet recover thin-file performance. |

The ablation workflow also includes a Dummy Classifier baseline and Brier score
for probability-quality review.

Current public benchmark:

| Dataset | Model | ROC-AUC | Brier score | Notes |
| --- | --- | ---: | ---: | --- |
| UCI Default of Credit Card Clients | Logistic Regression | 0.710 | 0.209 | Real public credit-card benchmark. |
| UCI Default of Credit Card Clients | Random Forest | 0.775 | 0.159 | Best current public benchmark result. |

This benchmark validates the pipeline on public credit-risk data, not on
Kazakhstan MFI borrowers.

See [PILOT_EVIDENCE_CLAIMS.md](PILOT_EVIDENCE_CLAIMS.md) for the current
claim boundary between implemented prototype evidence, synthetic-only evidence,
public benchmark evidence, assumptions, and blocked real-world validation.

Current error analysis at threshold `0.50`:

| Error Type | Count | Interpretation |
| --- | ---: | --- |
| False positive | 63 | Good borrowers could be wrongly flagged as high risk. |
| False negative | 221 | High-risk borrowers could be missed by the model. |

The most confident false negatives often have `late_payment_count = 0`, which
supports the current proxy-risk finding: repayment-history features dominate
the synthetic dataset.

Current threshold policy analysis:

| Policy | Auto Approval Rate | Manual Review Rate | Auto Decline Rate |
| --- | ---: | ---: | ---: |
| lender_protective | 0.127 | 0.265 | 0.608 |
| balanced_review | 0.278 | 0.243 | 0.479 |
| inclusion_first | 0.392 | 0.270 | 0.338 |
| starter_loan_review | 0.239 | 0.394 | 0.367 |

These policies are research scenarios, not recommended production policy.

Reproducible tables and plots are generated under
`reports/research-artifacts/` with:

```powershell
.venv\Scripts\python -m microscore --reports
```

## Calibration

The codebase now reports Brier score in model results and includes calibration
binning utilities. The reports command saves `calibration_bins.csv` and
`calibration_curve.png`. Calibration must still be validated before any
real-world pilot, because credit-risk probabilities need to be meaningful, not
only well-ranked.

KZT calibration is documented separately in
[KZT_CALIBRATION_ASSUMPTIONS.md](KZT_CALIBRATION_ASSUMPTIONS.md). Until that
evidence checklist is satisfied, monetary fields and Monte Carlo financial
outputs are prototype amount units, not calibrated KZT.

## Explainability

Current explanations:

- global feature importance;
- exact local additive log-odds explanations for the API Logistic Regression
  model;
- top positive and protective factors for individual applications;
- standard vs thin-file scenario comparison;
- proxy-sensitivity delta;
- analyst-facing decision-support recommendation.

Planned explanations:

- SHAP or TreeSHAP explanations for future nonlinear/tree models;
- richer false-positive and false-negative review;
- model cards for each future trained version.

## Human Oversight

MicroScore should support a loan officer or MFI analyst. It should not replace
human judgment. The API explicitly returns decision-support next steps such as
manual review, affordability review, and proxy-sensitive review.

The Monte Carlo Policy Lab is also a human-review aid. It simulates portfolio
outcome ranges from stored model probabilities, policy thresholds, and explicit
financial/stress assumptions. It does not change borrower scores or recommend
an automatic decision. Its loss probabilities and percentile ranges are not
validated forecasts or regulatory risk measures because the current model has
no real MFI repayment calibration.

Monetary outputs are prototype amount units, not calibrated KZT. The project
must satisfy the evidence checklist in
[KZT_CALIBRATION_ASSUMPTIONS.md](KZT_CALIBRATION_ASSUMPTIONS.md) before making
KZT-denominated profitability, loss, pricing, or capital claims.

## Ethical Risks

- Proxy discrimination through repayment-history or socioeconomic variables.
- Excluding good borrowers because they lack formal financial history.
- Over-reliance on synthetic-data performance.
- Unequal access for rural borrowers if digital behavior is treated too
  strongly.
- Incentive problems if borrowers learn to optimize superficial behaviors.

## Fairness Risks

Current audits slice by:

- gender;
- employment status;
- settlement type;
- Pavlodar district.

These audits are diagnostic. They do not prove fairness. Protected and
sensitive features should not be used blindly in lending decisions.

## Privacy Risks

Behavioral scoring can become invasive if it collects excessive data. The
project should prefer aggregated, consented, explainable signals and avoid
private messages, contact lists, exact location trails, social media content,
and opaque third-party data.

## Limitations

- Synthetic borrower-level data.
- Public benchmark is from Taiwan credit-card data, not Kazakhstan microfinance
  data.
- No real MFI repayment validation yet.
- No pilot evidence claim should exceed the boundary in
  [PILOT_EVIDENCE_CLAIMS.md](PILOT_EVIDENCE_CLAIMS.md).
- Regional access indices are hypotheses.
- No deployed public demo yet.
- No production-grade authentication or security review.
- No longitudinal repayment modeling yet.
- No SHAP explanations yet for nonlinear/tree model variants.

## Monitoring Needed Before Pilot

- Drift in feature distributions.
- Calibration drift.
- Segment-level approval and error rates.
- Proxy sensitivity to late-payment features.
- Proxy Monitoring v2 for repayment-history, monetary-scale, affordability,
  debt/formal-credit, and digital-access features.
- Manual review override rates.
- Borrower complaints and appeal outcomes.

## Owner

Alexandr Tereshkov, Pavlodar, Kazakhstan.
