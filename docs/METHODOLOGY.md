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

The API prototype also reports an application-level proxy-sensitivity check:
the standard score is compared with a separately trained thin-file model that
drops `late_payment_count`. This helps identify cases where the model's risk
estimate depends heavily on the strongest repayment-history proxy.

The API adds a decision-support layer on top of the model output. It converts
standard and thin-file scores into a human-review recommendation with rationale
and next steps. This is intentionally framed as analyst support, not automated
lending approval.

## Fairness And Segment Audits

The current audit layer reports metrics by:

- gender
- employment status
- Pavlodar district
- settlement type

The goal is not to use protected or sensitive features blindly in decisions.
The goal is to measure whether model behavior differs across groups and whether
threshold choices unintentionally reduce access for underserved borrowers.

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

1. Add calibration curves and Brier score reporting to the main notebook.
2. Create model cards for each model version.
3. Expand the no-repayment-history scenario with calibration and stability
   checks.
4. Add temporal features once longitudinal data exists.
5. Replace regional assumptions with official open data where possible.
6. Seek anonymized pilot data from a local MFI.
