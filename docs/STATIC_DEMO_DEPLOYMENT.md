# Static Demo Deployment

MicroScore now includes a static frontend demo that can be hosted without the
FastAPI backend. The hosted demo uses `apps/web/mock-api.js`, synthetic
in-browser data, and demo personas only.

## What Gets Deployed

The GitHub Pages workflow publishes the `apps/web/` directory:

- `index.html`
- `app.js`
- `mock-api.js`
- `styles.css`
- `assets/`

No database, API server, real borrower records, or model training artifacts are
deployed.

When the frontend is opened on a hosted domain, it automatically switches to
static demo mode. The sidebar hides local API settings, labels the connection as
a demo system, and keeps reviewers away from localhost ports.

## GitHub Pages Setup

1. Push the repository to GitHub.
2. Open repository settings.
3. Go to **Pages**.
4. Set **Source** to **GitHub Actions**.
5. Run the `Deploy static web demo` workflow or push to `main`.

The workflow is defined in:

```text
.github/workflows/pages.yml
```

The expected public URL is usually:

```text
https://alex-tereshkovv.github.io/micro-score/
```

## Demo Accounts

The hosted demo accepts the same demo accounts:

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
```

## Safety Notes

- The hosted demo is not a lending service.
- Do not enter real borrower data.
- All data shown in static mode is synthetic and browser-local.
- Static demo scores are illustrative only and are not model validation.

## Local Static Demo

Run the local web server and open:

```text
http://127.0.0.1:5173?demo=static
```

The query parameter forces static mode even if the FastAPI backend is not
running.
