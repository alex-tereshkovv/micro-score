# MicroScore: Interpretable Alternative Credit-Risk Modeling for Thin-File Borrowers in Pavlodar, Kazakhstan

## Abstract

MicroScore investigates whether behavioral financial signals can support
credit-risk review for thin-file borrowers in Pavlodar, Kazakhstan. The project
combines machine-learning baselines, leakage checks, proxy-risk analysis,
regional simulation, threshold analysis, and a small FastAPI/web product
prototype. Current results show that the full synthetic-data model can achieve
moderate ROC-AUC, but much of that performance depends on `late_payment_count`,
a strong repayment-history proxy. A separate UCI public benchmark now tests the
same pipeline on real public credit-card default data, where Random Forest
reaches ROC-AUC about `0.775`. The project therefore treats the current system
as a research and decision-support prototype, not a validated lending model.

## 1. Introduction

Traditional credit scoring can exclude borrowers who lack formal credit history,
stable official employment, or collateral. This is especially important in
regional and rural contexts where people may be economically active but poorly
represented in formal banking data.

MicroScore asks whether behavioral financial data can help identify responsible
borrowers while keeping lending risk visible to microfinance organizations.

## 2. Local Context

The project focuses on Pavlodar region. Public regional context shows a mix of
urban, industrial, peri-urban, and rural communities. This makes Pavlodar a
useful setting for studying financial inclusion, access gaps, and different
borrower contexts.

The current regional layer is not real borrower geography. It is a transparent
simulation scaffold that must be replaced with measured data before pilot use.

## 3. Related Work

Relevant areas include:

- alternative credit scoring;
- thin-file borrower risk modeling;
- explainable machine learning;
- model cards and responsible AI governance;
- fairness and proxy-risk auditing;
- financial inclusion and microfinance decision systems.

## 4. Data

The current borrower-level dataset is synthetic. It contains behavioral and
financial variables such as income, debt, digital banking activity, deposits,
spending, loan amount, open loans, and late-payment count.

The regional layer uses public context and explicit assumptions. Evidence-based
fields and assumptions are separated in `docs/DATA_STATEMENT.md`.

The project also includes a separate public benchmark track using UCI Default
of Credit Card Clients. This benchmark is not local to Kazakhstan, but it allows
the same modeling, calibration, feature-importance, and error-analysis workflow
to be tested on a real public credit-risk dataset.

## 5. Methodology

The current pipeline includes:

- feature engineering;
- leakage-feature removal;
- Logistic Regression and Random Forest baselines;
- scaling and one-hot encoding inside sklearn pipelines;
- stratified train/test split;
- 5-fold cross-validation;
- ROC-AUC, accuracy, precision, recall, F1, and Brier score;
- proxy-feature audit;
- feature-group ablation study;
- local additive explanations for individual API scores;
- false-positive and false-negative error analysis;
- approve/review/decline threshold policy analysis;
- saved research artifacts for metrics, ablation, calibration, and explanation
  review;
- segment/fairness audit;
- decision-threshold analysis;
- thin-file scenario without `late_payment_count`.

## 6. Leakage And Proxy Risk

The project drops target-like or unrealistic features:

- `customer_id`
- `credit_score`
- `loan_default_history`
- `fraud_flag`

The most important remaining concern is `late_payment_count`. In the current
synthetic dataset, it dominates model behavior and behaves like a strong proxy
for default.

## 7. Models

Current baselines:

- Logistic Regression
- Random Forest

The API prototype uses Logistic Regression because it is easier to explain and
because exact local additive contribution factors can be shown to an analyst.

## 8. Evaluation

### Research Finding 1

The full synthetic-data model achieves moderate ranking performance:

- Logistic Regression ROC-AUC: about `0.806`
- Random Forest ROC-AUC: about `0.830`

### Research Finding 2

The performance is heavily dependent on `late_payment_count`:

- single-feature ROC-AUC for `late_payment_count`: about `0.827`
- Logistic Regression ROC-AUC without `late_payment_count`: about `0.486`
- Random Forest ROC-AUC without `late_payment_count`: about `0.492`

This suggests that the current synthetic dataset does not yet contain enough
independent behavioral signal for reliable thin-file scoring.

### Research Finding 3

Feature-group ablation confirms the same weakness:

| Scenario | Logistic Regression ROC-AUC | Random Forest ROC-AUC | Interpretation |
| --- | ---: | ---: | --- |
| Raw all features | 0.966 | 1.000 | Diagnostic ceiling with leakage-like fields included. |
| No leakage baseline | 0.806 | 0.830 | Strong but dependent on repayment-history proxy signal. |
| No `late_payment_count` | 0.486 | 0.492 | Near-random thin-file stress test. |
| Behavioral only | 0.499 | 0.494 | Synthetic behavioral-only signal is weak. |
| Regional only | 0.551 | 0.551 | Simulated local context alone is not sufficient. |
| Behavioral + regional | 0.547 | 0.529 | Regional scaffold does not solve the thin-file problem yet. |

This makes the next data need clear: the project requires real, consented,
local repayment and behavioral data before claiming predictive validity.

### Research Finding 4

The public UCI benchmark runs successfully as a separate Experiment B:

| Model | ROC-AUC | Brier score | F1 |
| --- | ---: | ---: | ---: |
| Logistic Regression | 0.710 | 0.209 | 0.465 |
| Random Forest | 0.775 | 0.159 | 0.541 |

This strengthens the project because the modeling pipeline is no longer tested
only on synthetic data. However, it remains a Taiwan credit-card benchmark and
does not validate Pavlodar microfinance deployment.

### Research Finding 5

Error analysis shows an important failure mode. At a `0.50` threshold, the
Logistic Regression baseline has:

- `63` false positives;
- `221` false negatives;
- false-positive rate about `0.269`;
- false-negative rate about `0.289`.

The most confident false negatives often have `late_payment_count = 0`. This is
consistent with the ablation result: when repayment-history proxy information
is absent, the current synthetic data does not provide enough independent
behavioral signal to identify all high-risk borrowers.

### Research Finding 6

Three-zone threshold policies make the access-vs-risk trade-off concrete:

| Policy | Auto Approval Rate | Manual Review Rate | Auto Decline Rate | High-Risk Approval Rate |
| --- | ---: | ---: | ---: | ---: |
| lender_protective | 0.127 | 0.265 | 0.608 | 0.093 |
| balanced_review | 0.278 | 0.243 | 0.479 | 0.206 |
| inclusion_first | 0.392 | 0.270 | 0.338 | 0.289 |
| starter_loan_review | 0.239 | 0.394 | 0.367 | 0.172 |

This shows why the product should support analyst review rather than a simple
binary threshold. Different lending policies change inclusion and risk exposure
in opposite directions.

### Research Finding 6

Decision thresholds create a strong access-vs-sustainability trade-off. Under
the current lending assumptions, a purely profit-maximizing threshold can
approve almost nobody. The project therefore reports constrained thresholds and
segment approval rates instead of optimizing only for profit.

## 9. Decision Threshold Analysis

The threshold module estimates:

- approval rate;
- default rate among approved borrowers;
- good-borrower rejection rate;
- bad-borrower approval rate;
- expected profit/loss;
- segment approval rates.

This reframes credit scoring as a decision system rather than a pure
classification problem.

## 10. Fairness And Segment Audit

The current audit reports segment metrics by:

- gender;
- employment status;
- Pavlodar district;
- settlement type.

These audits are exploratory and cannot prove fairness without real data.

## 11. Product Prototype

The project includes:

- FastAPI backend;
- SQLite local persistence;
- borrower, MFI analyst, and admin roles;
- application submission;
- MFI scoring;
- segment analytics;
- audit trail;
- static web frontend;
- local positive/protective explanation factors;
- false-positive and false-negative research reports;
- threshold policy reports;
- generated `reports/research-artifacts/` outputs;
- decision-support recommendations.

## 12. Limitations

- Borrower-level data is synthetic.
- Regional features are partly assumptions.
- Public benchmark metrics come from Taiwan credit-card data, not Kazakhstan
  microfinance data.
- No real MFI validation yet.
- No public deployed demo yet.
- No SHAP explanations yet for nonlinear/tree model variants.
- No longitudinal repayment modeling yet.
- No production security review yet.

## 13. Future Work

- Replace assumptions with official and measured local indicators.
- Compare synthetic Pavlodar and UCI benchmark failure modes in the research
  paper and model card.
- Add SHAP or TreeSHAP explanations for nonlinear/tree model variants.
- Track generated report artifacts over model versions.
- Expand false-positive and false-negative case analysis with stakeholder
  review.
- Seek anonymized pilot data from an MFI.
- Deploy a public demo and record a two-minute walkthrough video.
- Explore game-theoretic incentives after the scoring workflow stabilizes.

## 14. Conclusion

MicroScore is strongest when it is honest about uncertainty. The current model
is not a real-world validated lending system. Its value is that it exposes the
core research problem clearly: alternative credit scoring must distinguish real
behavioral signal from leakage, proxy variables, and unfair access barriers.
