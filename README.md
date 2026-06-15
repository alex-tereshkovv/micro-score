# MicroScore

![CI](https://github.com/alex-tereshkovv/micro-score/actions/workflows/ci.yml/badge.svg)

Interpretable alternative credit-risk scoring prototype for thin-file borrowers
in Pavlodar, Kazakhstan.

## Snapshot

| Field | Status |
| --- | --- |
| Project type | Research + product prototype |
| Region | Pavlodar region, Kazakhstan |
| Borrower focus | Thin-file and underserved borrowers |
| Product | FastAPI API + static web prototype |
| Models | Logistic Regression, Random Forest |
| Current demo | One-click local demo + static web demo mode |
| Public demo | GitHub Pages workflow ready for static demo hosting |
| Quality gate | GitHub Actions CI for tests, smoke checks, and static demo |
| Main finding | Synthetic-data performance depends heavily on `late_payment_count` |
| Key limitation | Borrower-level data is synthetic, not real MFI data |
| Public benchmark | UCI Default of Credit Card Clients: RF ROC-AUC `0.775` |
| Next research upgrade | Compare benchmark and synthetic failure modes |

## Reviewer Assets

- Live Demo: static frontend mode is ready; public hosting planned in `docs/PUBLIC_DEMO_PLAN.md`
- Demo Video: planned; script in [docs/DEMO_VIDEO_SCRIPT.md](docs/DEMO_VIDEO_SCRIPT.md)
- Research Paper PDF: planned
- Research paper draft: [docs/RESEARCH_PAPER.md](docs/RESEARCH_PAPER.md)
- Model card: [docs/MODEL_CARD.md](docs/MODEL_CARD.md)
- Data statement: [docs/DATA_STATEMENT.md](docs/DATA_STATEMENT.md)
- Benchmark pipeline: [docs/BENCHMARK_DATASETS.md](docs/BENCHMARK_DATASETS.md)
- API contract: [docs/API_CONTRACT.md](docs/API_CONTRACT.md)
- Product roadmap: [docs/PRODUCT_ROADMAP.md](docs/PRODUCT_ROADMAP.md)
- Static demo deployment: [docs/STATIC_DEMO_DEPLOYMENT.md](docs/STATIC_DEMO_DEPLOYMENT.md)
- Engineering quality: [docs/ENGINEERING_QUALITY.md](docs/ENGINEERING_QUALITY.md)
- Demo walkthrough: [docs/DEMO_WALKTHROUGH.md](docs/DEMO_WALKTHROUGH.md)
- Screenshot checklist: [docs/SCREENSHOT_CHECKLIST.md](docs/SCREENSHOT_CHECKLIST.md)
- Release checklist: [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)

## Why This Matters

In rural Kazakhstan, a large share of adults lack a formal credit history.
Traditional banks can reject them because they have no credit file, no official
employment history, or no collateral. At the same time, many of these people
may still be disciplined and responsible borrowers.

Microfinance organizations need better ways to estimate risk in these contexts,
especially outside large cities. MicroScore tests whether behavioral banking
data can help make credit access more inclusive while still keeping lending
decisions sustainable for MFIs.

## Research Findings

1. The current synthetic-data model reaches moderate ROC-AUC: Logistic
   Regression about `0.806`, Random Forest about `0.830`.
2. The result is fragile: `late_payment_count` alone has ROC-AUC about `0.827`,
   and removing it drops ROC-AUC to about `0.486-0.492`.
3. Thin-file stress tests are weak on the current synthetic dataset. This is a
   useful finding, not a failure: it shows that real or public benchmark data is
   needed before making stronger claims.
4. Threshold analysis shows a real access-vs-sustainability trade-off: a purely
   profit-maximizing policy can approve almost nobody under the current
   assumptions.
5. Public UCI benchmark validation now runs separately. On UCI Default of
   Credit Card Clients, Random Forest reaches ROC-AUC about `0.775` and Brier
   score about `0.159`.

These are research findings, not proof that the model is ready for real
lending.

## Demo Status

MicroScore currently has a one-click local demo launcher for Windows and a
static frontend demo mode for portfolio hosting. The static mode uses synthetic
mock data in the browser only; it is not a lending service and does not collect
real borrower data. A GitHub Pages workflow is included; deployment steps are
documented in [docs/STATIC_DEMO_DEPLOYMENT.md](docs/STATIC_DEMO_DEPLOYMENT.md).

## Local Quick Start

Install dependencies:

```powershell
# Windows
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
# macOS/Linux
.venv/bin/python -m pip install -r requirements.txt
```

Run the research pipeline:

```powershell
# Windows
.venv\Scripts\python -m microscore --reports
```

```bash
# macOS/Linux
.venv/bin/python -m microscore --reports
```

Run the local product demo:

```powershell
# Windows, one command
.\Start-MicroScore.cmd
```

The launcher seeds demo data, starts the API and web UI, opens the browser, and
stops both local servers when the launcher window is closed.

Manual fallback:

```powershell
# Windows terminal 1
.venv\Scripts\python -m microscore_api.seed
.venv\Scripts\python -m uvicorn microscore_api.main:app --host 127.0.0.1 --port 8010 --reload

# Windows terminal 2
.venv\Scripts\python -m http.server 5173 --bind 127.0.0.1 --directory apps\web
```

```bash
# macOS/Linux terminal 1
.venv/bin/python -m microscore_api.seed
.venv/bin/python -m uvicorn microscore_api.main:app --host 127.0.0.1 --port 8010 --reload
```

```bash
# macOS/Linux terminal 2
.venv/bin/python -m http.server 5173 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:5173` for manual fallback. The web UI auto-detects the
local API on common development ports.

Static frontend demo mode: `http://127.0.0.1:5173?demo=static`. This mode
works without FastAPI by using a synthetic in-browser demo portfolio.

Demo accounts use password `password123`:

- `borrower@test.com`
- `analyst@test.com`
- `admin@test.com`

## Product Prototype

The web prototype supports:

- borrower login/register and loan application submission
- application timeline/status history
- MFI application queue
- MFI portfolio CSV export
- risk scoring with local explanations
- standard vs thin-file scoring scenario
- analyst decision capture
- MFI review packet with governance flags and checklist items
- decision audit by risk band, district, proxy sensitivity, and recommendation
- Policy Lab for approve/review/decline threshold trade-offs
- admin audit trail and application clearing

## Research Scope

MicroScore currently has two research tracks:

- Experiment A: synthetic Pavlodar-oriented prototype data for product and
  local-context design.
- Experiment B: public benchmark validation using real public credit-risk
  datasets. The first implemented benchmark is UCI Default of Credit Card
  Clients, with artifacts in `reports/benchmark-artifacts/`.

The Pavlodar regional layer is a transparent research scaffold, not real MFI
borrower geography. Public-context assumptions and sources are documented in
[data/external/README.md](data/external/README.md).

## Useful Commands

```powershell
# Windows
.venv\Scripts\python -m microscore --audit
.venv\Scripts\python -m microscore --ablation
.venv\Scripts\python -m microscore --regional --decision
.venv\Scripts\python -m microscore --policy-analysis
# After placing the UCI file under data\external\benchmarks\...
.venv\Scripts\python -m microscore --benchmark uci-default
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
node scripts\static-demo-smoke.js
```

```bash
# macOS/Linux
.venv/bin/python -m microscore --audit
.venv/bin/python -m microscore --ablation
.venv/bin/python -m microscore --regional --decision
.venv/bin/python -m microscore --policy-analysis
# After placing the UCI file under data/external/benchmarks/...
.venv/bin/python -m microscore --benchmark uci-default
```

## Project Map

- `apps/web/` - static browser prototype
- `src/microscore/` - research pipeline
- `src/microscore_api/` - FastAPI product prototype
- `data/raw/` - current synthetic dataset
- `data/external/` - public Pavlodar regional context
- `data/external/benchmarks/` - public benchmark dataset instructions
- `docs/` - research, governance, benchmark, demo, and API documentation
- `reports/research-artifacts/` - generated metrics, plots, and tables
- `reports/benchmark-artifacts/` - generated public benchmark outputs
- `tests/` - unit, integration, API, and static frontend tests

## Author

Alexandr

Pavlodar, Kazakhstan

This project started from a simple observation: people in my region get
rejected for loans simply because they have no credit history. I am building
MicroScore to test whether behavioral data could help.

My goal is not to claim that a synthetic model can solve lending. My goal is to
build a careful, interpretable research prototype that can grow into a real
pilot with public benchmarks, local validation, and human oversight.
