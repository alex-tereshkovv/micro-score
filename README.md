# MicroScore

Interpretable alternative credit-risk scoring prototype for thin-file borrowers
in Pavlodar, Kazakhstan.

## Snapshot

| Field | Status |
| --- | --- |
| Project type | Research + product prototype |
| Region | Pavlodar region, Kazakhstan |
| Borrower focus | Thin-file and underserved borrowers |
| Models | Logistic Regression, Random Forest |
| Product | FastAPI API + static web prototype |
| Current demo | Local demo at `http://127.0.0.1:5173` |
| Public demo | Planned; not deployed yet |
| Research artifacts | Saved under `reports/research-artifacts/` |
| Main finding | Current synthetic-data performance depends heavily on `late_payment_count` |
| Key limitation | Borrower-level data is synthetic and not real MFI data |
| Next step | Public-data validation, live demo, SHAP/TreeSHAP for nonlinear models, and pilot-data outreach |

## Quick Links

- [Research paper draft](docs/RESEARCH_PAPER.md)
- [Model card](docs/MODEL_CARD.md)
- [Data statement](docs/DATA_STATEMENT.md)
- [Impact plan](docs/IMPACT.md)
- [Stakeholder interview guide](docs/STAKEHOLDER_INTERVIEW_GUIDE.md)
- [Validation tracker](docs/VALIDATION_TRACKER.md)
- [Methodology](docs/METHODOLOGY.md)
- [Product roadmap](docs/PRODUCT_ROADMAP.md)
- [API contract](docs/API_CONTRACT.md)

## Research Findings

1. The full synthetic-data model reaches moderate ROC-AUC:
   Logistic Regression about `0.806`, Random Forest about `0.830`.
2. The result is fragile: `late_payment_count` alone has ROC-AUC about `0.827`,
   and removing it drops ROC-AUC to about `0.486-0.492`.
3. Threshold analysis shows a real access-vs-sustainability trade-off: a
   purely profit-maximizing policy can approve almost nobody under the current
   assumptions.
4. Ablation study confirms that behavioral-only and behavioral-plus-regional
   scenarios are still weak in the current synthetic dataset. This is the main
   evidence that real pilot data is the next research bottleneck.

These findings are intentionally presented as research findings, not as proof
that the model is ready for real lending.

## Demo Status

The current demo runs locally:

```powershell
.venv\Scripts\python -m microscore_api.seed
.venv\Scripts\python -m uvicorn microscore_api.main:app --host 127.0.0.1 --port 8010 --reload
```

```powershell
.venv\Scripts\python -m http.server 5173 --bind 127.0.0.1 --directory apps\web
```

Open `http://127.0.0.1:5173` and set API base to
`http://127.0.0.1:8010`.

The seed command creates the three main demo accounts plus a scored portfolio
of 20 Pavlodar-region loan applications. That gives the MFI queue, segment
analytics, and Policy Lab useful data immediately after startup.

Planned portfolio additions:

- public frontend deployment;
- hosted API or simplified Streamlit demo;
- two-minute demo video;
- PDF version of the research paper.

## Research Artifacts

MicroScore can generate reproducible research artifacts:

```powershell
.venv\Scripts\python -m microscore --reports
```

This writes:

- `reports/research-artifacts/SUMMARY.md`
- `reports/research-artifacts/model_metrics.csv`
- `reports/research-artifacts/ablation_study.csv`
- `reports/research-artifacts/calibration_bins.csv`
- `reports/research-artifacts/error_analysis_summary.csv`
- `reports/research-artifacts/segment_error_analysis.csv`
- `reports/research-artifacts/false_positive_examples.csv`
- `reports/research-artifacts/false_negative_examples.csv`
- `reports/research-artifacts/prediction_errors.csv`
- `reports/research-artifacts/policy_analysis.csv`
- `reports/research-artifacts/segment_policy_analysis.csv`
- `reports/research-artifacts/example_explanation_summary.csv`
- `reports/research-artifacts/example_explanation_factors.csv`
- `reports/research-artifacts/calibration_curve.png`
- `reports/research-artifacts/ablation_roc_auc.png`

These files make the project easier to review quickly: the key metrics,
ablation findings, calibration bins, false-positive/false-negative analysis,
threshold policy analysis, and one local explanation example are available
without rerunning notebooks.

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
- ROC-AUC, Brier score, accuracy, precision, recall, and F1
- feature-importance analysis
- local additive explanations for individual API scores
- feature-group ablation study
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

## Feature Ablation Study

The project now includes an ablation mode:

```bash
.venv\Scripts\python -m microscore --ablation
```

Current synthetic-data results:

| Scenario | Logistic Regression ROC-AUC | Random Forest ROC-AUC | Interpretation |
| --- | ---: | ---: | --- |
| Raw all features | 0.966 | 1.000 | Diagnostic ceiling; includes leakage-like fields. |
| No leakage baseline | 0.806 | 0.830 | Strong but still depends on `late_payment_count`. |
| No `late_payment_count` | 0.486 | 0.492 | Near-random thin-file stress test. |
| Behavioral only | 0.499 | 0.494 | Current synthetic behavioral signal is weak. |
| Regional only | 0.551 | 0.551 | Simulated geography alone carries weak signal. |
| Behavioral + regional | 0.547 | 0.529 | Regional scaffold does not yet solve thin-file scoring. |

The ablation table includes a Dummy Classifier baseline and Brier score, so the
project can compare ranking quality and probability quality instead of relying
only on accuracy.

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

The project also includes three-zone policy analysis:

```bash
.venv\Scripts\python -m microscore --policy-analysis
```

This compares `approve`, `manual review`, and `decline` regions for policies
such as `lender_protective`, `balanced_review`, and `inclusion_first`.

## Research And Product Docs

The project now has research, governance, and product documents:

- [Research Paper Draft](docs/RESEARCH_PAPER.md): academic-style project
  writeup with findings, limitations, and future work.
- [Model Card](docs/MODEL_CARD.md): intended use, non-use, metrics, risks,
  fairness concerns, and oversight requirements.
- [Data Statement](docs/DATA_STATEMENT.md): synthetic-data disclosure,
  evidence/assumption split, public sources, and pilot-data needs.
- [Impact Plan](docs/IMPACT.md): local motivation, stakeholder plan, possible
  harms, and future pilot path.
- [Methodology](docs/METHODOLOGY.md): research question, leakage policy,
  feature groups, evaluation metrics, fairness audits, and current limitations.
- [Product Roadmap](docs/PRODUCT_ROADMAP.md): five-month plan toward a working
  application with borrower login, loan applications, MFI analytics, and model
  governance.
- [API Contract](docs/API_CONTRACT.md): backend roles, endpoints, response
  schemas, and borrower form fields for the future frontend.

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

Seed demo users and a scored Pavlodar demo portfolio:

```bash
.venv\Scripts\python -m microscore_api.seed
```

Demo accounts use password `password123`:

- `borrower@test.com`
- `analyst@test.com`
- `admin@test.com`

Current API scope:

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `GET /me`
- `POST /applications`
- `GET /applications/{application_id}`
- `GET /mfi/applications`
- `POST /mfi/applications/{application_id}/score`
- `POST /mfi/applications/{application_id}/decision`
- `GET /mfi/analytics/segments`
- `GET /mfi/analytics/policies`
- `GET /mfi/analytics/decisions`
- `GET /admin/audit-events`
- `DELETE /admin/applications`

The current API uses SQLite persistence by default:

```text
data/app/microscore.sqlite3
```

The database path can be changed with `MICROSCORE_API_DB_PATH`. Runtime database
files are ignored by Git; only `data/app/.gitkeep` is tracked.

The API flow is covered by integration tests: borrower registration,
application submission, MFI scoring, analyst decision capture, decision audit
analytics, segment analytics, policy analytics, and admin audit events.
OpenAPI now exposes typed response schemas for applications, score results,
segment analytics, policy analytics, decision analytics, and audit events.

Loan applications persist in SQLite until an admin clears them or the local
database file is removed. The current demo values use the synthetic dataset's
prototype numeric scale, not calibrated real KZT amounts.

Scoring now reports two scenarios for each application:

- standard model
- thin-file model without `late_payment_count`

This makes proxy sensitivity visible instead of hiding it behind one risk band.
The API also returns a decision-support recommendation with rationale and next
steps, so an MFI analyst sees what to review instead of receiving only a raw
probability.

The scoring response now includes a local explanation object. For the current
Logistic Regression API model, this is an exact additive log-odds explanation:
baseline log-odds plus feature contributions equals the model's predicted
log-odds. The frontend separates factors that raise predicted risk from factors
that lower predicted risk.

## Web Prototype

MicroScore also includes a static frontend prototype under `apps/web/`. It
connects to the local API and supports:

- borrower login/register
- borrower loan application form
- application status lookup
- MFI application queue
- application scoring
- MFI analyst decision capture
- portfolio overview with risk-band, district, policy-mix, and decision charts
- decision audit by risk band, district, proxy sensitivity, and recommendation
- segment analytics
- Policy Lab for approve/review/decline threshold trade-offs
- admin audit trail

Start the API:

```powershell
.venv\Scripts\python -m microscore_api.seed
.venv\Scripts\python -m uvicorn microscore_api.main:app --reload
```

Start the web UI in another PowerShell window:

```powershell
.venv\Scripts\python -m http.server 5173 --directory apps\web
```

Open:

```text
http://127.0.0.1:5173
```

## Project Structure

```text
MicroScore/
|-- apps/
|   `-- web/
|       |-- README.md
|       |-- assets/
|       |   |-- apple-touch-icon.png
|       |   |-- favicon.svg
|       |   |-- favicon-32.png
|       |   |-- microscore-mark.svg
|       |   `-- micro-score.png
|       |-- app.js
|       |-- index.html
|       `-- styles.css
|-- docs/
|   |-- API_CONTRACT.md
|   |-- DATA_STATEMENT.md
|   |-- IMPACT.md
|   |-- METHODOLOGY.md
|   |-- MODEL_CARD.md
|   |-- PRODUCT_ROADMAP.md
|   `-- RESEARCH_PAPER.md
|-- notebooks/
|   `-- credit_analysis.ipynb
|-- reports/
|   |-- README.md
|   `-- research-artifacts/
|       |-- SUMMARY.md
|       |-- ablation_study.csv
|       |-- calibration_bins.csv
|       |-- error_analysis_summary.csv
|       |-- example_explanation_factors.csv
|       |-- example_explanation_summary.csv
|       |-- false_negative_examples.csv
|       |-- false_positive_examples.csv
|       |-- manifest.json
|       |-- model_metrics.csv
|       |-- policy_analysis.csv
|       |-- prediction_errors.csv
|       |-- segment_error_analysis.csv
|       |-- segment_policy_analysis.csv
|       |-- ablation_roc_auc.png
|       `-- calibration_curve.png
|-- data/
|   |-- README.md
|   |-- external/
|   |   |-- README.md
|   |   `-- pavlodar_district_profiles.csv
|   |-- app/
|   |   `-- .gitkeep
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
|   |   |-- ablation.py
|   |   |-- audit.py
|   |   |-- cli.py
|   |   |-- decision.py
|   |   |-- error_analysis.py
|   |   |-- explainability.py
|   |   |-- features.py
|   |   |-- modeling.py
|   |   |-- paths.py
|   |   |-- reporting.py
|   |   `-- regional.py
|   |-- microscore_api/
|   |   |-- __init__.py
|   |   |-- database.py
|   |   |-- main.py
|   |   |-- scoring.py
|   |   |-- schemas.py
|   |   |-- security.py
|   |   `-- seed.py
|   `-- train_model.py
|-- tests/
|   |-- test_audit.py
|   |-- test_api_database.py
|   |-- test_api_integration.py
|   |-- test_api_seed.py
|   |-- test_api_scoring.py
|   |-- test_ablation.py
|   |-- test_decision.py
|   |-- test_error_analysis.py
|   |-- test_explainability.py
|   |-- test_features.py
|   |-- test_modeling.py
|   |-- test_reporting.py
|   |-- test_regional.py
|   `-- test_web_static.py
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

To run the feature-group ablation study:

```bash
.venv\Scripts\python -m microscore --ablation
```

To run false-positive and false-negative analysis:

```bash
.venv\Scripts\python -m microscore --error-analysis
```

To compare approve/review/decline policies:

```bash
.venv\Scripts\python -m microscore --policy-analysis
```

To generate reproducible research artifacts:

```bash
.venv\Scripts\python -m microscore --reports
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
