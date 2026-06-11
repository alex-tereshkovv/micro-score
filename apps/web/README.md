# MicroScore Web Prototype

Static browser frontend for the MicroScore API prototype.

Brand assets live at:

```text
apps/web/assets/favicon.svg
apps/web/assets/favicon-32.png
apps/web/assets/apple-touch-icon.png
apps/web/assets/microscore-mark.svg
apps/web/assets/micro-score.png
```

## Run

From the project root, start the API:

```powershell
.venv\Scripts\python -m microscore_api.seed
.venv\Scripts\python -m uvicorn microscore_api.main:app --reload
```

The seed command creates the main demo accounts and a scored 20-application
Pavlodar-region application portfolio, so the MFI tab is populated as soon as
the API starts.

In another PowerShell window, start the web UI:

```powershell
.venv\Scripts\python -m http.server 5173 --directory apps\web
```

Open:

```text
http://127.0.0.1:5173
```

Demo accounts:

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
```

Applications are stored in the local SQLite database until an admin clears them
from the Admin tab or the local database file is removed.

The MFI tab includes a Portfolio Overview with risk-band, district, policy-mix,
and analyst-decision charts, plus a Decision Audit table comparing recorded
analyst decisions with risk bands, districts, proxy sensitivity, and model
recommendations. The Policy Lab compares approve/review/decline threshold
policies on scored applications. These are predicted-probability previews, not
validated lending policies.
