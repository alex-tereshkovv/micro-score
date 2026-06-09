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
