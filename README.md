# MicroScore

Alternative behavioral credit scoring for underserved borrowers in Kazakhstan,
with an initial focus on Pavlodar and Pavlodar region.

## Why This Matters

In rural Kazakhstan, a large share of adults lack a formal credit history.
Traditional banks can reject them because they have no credit file, no official
employment history, or no collateral. At the same time, many of these people
may still be disciplined and responsible borrowers.

Microfinance organizations need better ways to estimate risk in these contexts,
especially outside large cities. MicroScore tests whether behavioral banking
data can help make credit access more inclusive while still keeping lending
decisions sustainable for MFIs.

## Project Idea

MicroScore explores whether digital and financial behavior can help estimate
credit risk when traditional bank signals are weak or unavailable. The project
is intended for research and prototyping, not for automatic lending decisions.

The core question is:

> Can behavioral banking data make microcredit more accessible while keeping
> risk manageable for microfinance organizations?

## Current Modeling Approach

The project trains and compares:

- Logistic Regression
- Random Forest

The pipeline includes:

- behavioral feature engineering
- one-hot encoding for categorical variables
- median/mode imputation
- numeric scaling inside sklearn `Pipeline`
- stratified train/test split
- 5-fold cross-validation
- ROC-AUC, accuracy, precision, recall, and F1
- feature-importance analysis
- basic leakage protection

## Leakage Policy

The model intentionally drops columns that are unrealistic or too close to the
answer for this research stage:

- `customer_id`
- `credit_score`
- `loan_default_history`
- `fraud_flag`

This keeps the experiment closer to the behavioral-scoring idea instead of
letting the model reuse existing credit reputation or target-like signals.

## Proxy And Fairness Audit

The project now includes an audit mode:

```bash
.venv\Scripts\python -m microscore --audit
```

Current synthetic-data findings:

- `late_payment_count` is a very strong proxy signal by itself: single-feature
  ROC-AUC is about `0.827`.
- For `late_payment_count >= 4`, the current synthetic dataset has a high-risk
  rate of `1.0`, which is unrealistically sharp.
- Removing `late_payment_count` drops ROC-AUC for both Logistic Regression and
  Random Forest to roughly `0.49`, meaning the current dataset relies heavily
  on that one signal.
- Segment metrics are reported by `gender` and `employment_status`, including
  predicted high-risk rate, recall, false-positive rate, and false-negative
  rate.

This does not automatically mean `late_payment_count` is forbidden. It means the
project should treat it as a sensitive modeling decision: useful for risk, but
possibly too close to traditional repayment history for a behavioral-scoring
experiment focused on people with thin or missing credit files.

## Project Structure

```text
MicroScore/
|-- notebooks/
|   `-- credit_analysis.ipynb
|-- data/
|   |-- README.md
|   |-- interim/
|   |-- processed/
|   `-- raw/
|       `-- credit_risk_dataset.csv
|-- scripts/
|   `-- check.ps1
|-- src/
|   |-- microscore/
|   |   |-- __init__.py
|   |   |-- __main__.py
|   |   |-- audit.py
|   |   |-- cli.py
|   |   |-- features.py
|   |   `-- modeling.py
|   `-- train_model.py
|-- tests/
|   |-- test_audit.py
|   `-- test_features.py
|-- .gitignore
|-- README.md
`-- requirements.txt
```

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[notebook]"
.venv\Scripts\python -m microscore
```

To run the proxy and segment audit:

```bash
.venv\Scripts\python -m microscore --audit
```

To work interactively:

```bash
.venv\Scripts\jupyter notebook notebooks/credit_analysis.ipynb
```

To run the local check script on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

## Dataset

The current dataset is synthetic and contains 5,000 rows. It is useful for
pipeline development, leakage checks, and experiment design, but it should not
be treated as proof that the model will work on real clients.

## Next Research Steps

1. Add better temporal features, such as behavior changes over time.
2. Compare urban and rural borrower segments.
3. Add fairness and stability checks.
4. Test graph-based or sequence-based models when suitable data exists.
5. Explore game-theoretic incentives: how borrowers and lenders may adapt when
   a scoring system becomes known.
6. Seek anonymized pilot data from a local MFI.

## Author

Alexandr

Pavlodar, Kazakhstan

This project started from a simple observation: people in my region get
rejected for loans simply because they have no credit history. I am building
MicroScore to test whether behavioral data could help.
