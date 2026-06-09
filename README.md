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
- simulated Pavlodar-region context for research demos
- one-hot encoding for categorical variables
- median/mode imputation
- numeric scaling inside sklearn `Pipeline`
- stratified train/test split
- 5-fold cross-validation
- ROC-AUC, accuracy, precision, recall, and F1
- feature-importance analysis
- decision-threshold and expected-loss analysis
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

## Pavlodar Regional Layer

The public dataset does not contain borrower-level geography, so MicroScore now
has a transparent Pavlodar regional layer. The district/city list and 2023
population weights are stored in
`data/external/pavlodar_district_profiles.csv`; they are based on public
administrative population tables. The access and seasonality indices are still
explicit modeling assumptions.

The layer adds reproducible fields such as:

- `pavlodar_district`
- `settlement_type`
- `distance_to_pavlodar_km`
- `regional_digital_access_index`
- `mfi_branch_access_index`
- `seasonal_income_risk`
- `financial_access_gap`

This layer is not presented as real MFI data. It is a research scaffold for
asking better local questions: how risk, access, and model behavior differ
between Pavlodar city, industrial cities, peri-urban areas, and rural districts.

Current public-context sources are documented in `data/external/README.md`.

Run it with:

```bash
.venv\Scripts\python -m microscore --regional
```

## Decision Analysis

Credit scoring is not only classification. The project now includes threshold
analysis that estimates:

- approval rate
- default rate among approved borrowers
- good-borrower rejection rate
- bad-borrower approval rate
- expected profit/loss under lending assumptions
- approval fairness by district, settlement type, and gender

Run it with:

```bash
.venv\Scripts\python -m microscore --regional --decision
```

Current synthetic-data finding: with the default assumptions, a purely
profit-maximizing lender would approve almost nobody. The project therefore also
reports a selected threshold with a minimum approval-rate constraint. This makes
the access-vs-sustainability trade-off explicit instead of hiding it behind one
accuracy number.

## Research And Product Docs

The project now has two planning documents:

- [Methodology](docs/METHODOLOGY.md): research question, leakage policy,
  feature groups, evaluation metrics, fairness audits, and current limitations.
- [Product Roadmap](docs/PRODUCT_ROADMAP.md): five-month plan toward a working
  application with borrower login, loan applications, MFI analytics, and model
  governance.

## Product API Prototype

MicroScore now includes an optional FastAPI prototype under `src/microscore_api/`.
It is the first backend step toward the future product: borrower accounts,
application submission, MFI review, and model scoring.

Install app dependencies when you want to run the API:

```bash
.venv\Scripts\python -m pip install -e ".[app]"
```

Run the local API:

```bash
.venv\Scripts\python -m uvicorn microscore_api.main:app --reload
```

Current API scope:

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `GET /me`
- `POST /applications`
- `GET /applications/{application_id}`
- `GET /mfi/applications`
- `POST /mfi/applications/{application_id}/score`
- `GET /mfi/analytics/segments`

The current API uses in-memory storage. This is intentional for the first
prototype; PostgreSQL and persistent audit logs are the next product milestone.

## Project Structure

```text
MicroScore/
|-- docs/
|   |-- METHODOLOGY.md
|   `-- PRODUCT_ROADMAP.md
|-- notebooks/
|   `-- credit_analysis.ipynb
|-- data/
|   |-- README.md
|   |-- external/
|   |   |-- README.md
|   |   `-- pavlodar_district_profiles.csv
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
|   |   |-- decision.py
|   |   |-- features.py
|   |   |-- modeling.py
|   |   |-- paths.py
|   |   `-- regional.py
|   |-- microscore_api/
|   |   |-- __init__.py
|   |   |-- main.py
|   |   `-- scoring.py
|   `-- train_model.py
|-- tests/
|   |-- test_audit.py
|   |-- test_api_scoring.py
|   |-- test_decision.py
|   |-- test_features.py
|   `-- test_regional.py
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

To run the regional and decision analysis:

```bash
.venv\Scripts\python -m microscore --regional --decision
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

The canonical dataset path is `data/raw/credit_risk_dataset.csv`. A legacy copy
may exist under `notebooks/data/` only so older notebook cells do not break.

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
