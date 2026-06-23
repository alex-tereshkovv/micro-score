# MicroScore Web Prototype

Static browser frontend for the MicroScore API prototype. It can run against
the local FastAPI backend or in static demo mode with synthetic in-browser
data.

Brand assets live at:

```text
apps/web/assets/favicon.svg
apps/web/assets/favicon-32.png
apps/web/assets/apple-touch-icon.png
apps/web/assets/microscore-mark.svg
apps/web/assets/micro-score.png
apps/web/assets/micro-score-lockup.png
```

## Run

From the project root, double-click:

```text
Start-MicroScore.cmd
```

Or run:

```powershell
.\Start-MicroScore.cmd
```

The launcher seeds demo data, starts the API, starts the static web UI, and
opens the browser automatically. Close the launcher window to stop the local
servers.

Manual fallback for development:

```powershell
.venv\Scripts\python -m microscore_api.seed
.venv\Scripts\python -m uvicorn microscore_api.main:app --host 127.0.0.1 --port 8010 --reload
```

The seed command creates the main demo accounts and a scored 20-application
Pavlodar-region application portfolio, so the MFI tab is populated as soon as
the API starts.

In another terminal, start the web UI:

```powershell
.venv\Scripts\python -m http.server 5173 --bind 127.0.0.1 --directory apps\web
```

Open:

```text
http://127.0.0.1:5173
```

Static demo mode without FastAPI:

```text
http://127.0.0.1:5173?demo=static
```

Static demo mode uses `mock-api.js` and synthetic data only. It is designed for
a future GitHub Pages/Vercel portfolio demo, not for real borrower data.

Demo accounts:

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
```

Applications are stored in the local SQLite database until an admin clears them
from the Admin tab or the local database file is removed.

The borrower workspace automatically lists the signed-in account's applications
with a visual lifecycle from submission through a terminal MFI decision. Its
API view excludes internal scores, staff identity, and analyst notes. Application
Intake v2 adds field-level feedback and a strict shared allowlist for ranges,
count fields, categories, and district/settlement consistency; the FastAPI
schema remains authoritative. MFI
application cards retain the full scoring and decision timeline. The MFI tab includes a
Portfolio Overview with risk-band, district, policy-mix, and analyst-decision
charts, a CSV export for the application queue, plus a Decision Audit table
comparing recorded analyst decisions with risk bands, districts, proxy
sensitivity, and model recommendations. Selecting an application automatically
opens Risk Detail v2 with lifecycle actions, affordability screening, governance
flags, local explanations, timeline events, the review checklist, and the full
decision history. The Policy Lab compares approve/review/decline
threshold policies on scored applications. The Monte Carlo Lab adds seeded,
paired baseline/adverse/severe portfolio simulations with explicit margin,
LGD, operating-cost, review-conversion, macro, and calibration assumptions. It
also shows numerical standard-error diagnostics and a tenant-scoped recent-run
registry keyed by a scored-portfolio SHA-256 fingerprint.
These are predicted-probability scenario previews, not forecasts or validated
lending policies.
