# Engineering Quality

MicroScore is a research and product prototype, so the quality goal is not only
model performance. The project should remain reproducible, reviewable, and safe
to demo as the codebase grows.

## Local Checks

Use the local check script on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

It runs:

- unit and integration tests
- Python syntax compilation
- research pipeline smoke test
- regional decision smoke test

## Static Demo Smoke Test

The public-demo layer has its own Node smoke test:

```powershell
node scripts\static-demo-smoke.js
```

The smoke test verifies that the in-browser static backend can:

- sign in as an MFI analyst
- load the seeded application queue
- score an application
- open a review packet
- switch the active model registry version and detect a stale score
- re-score with the newly active model and preserve its governance snapshot
- reproduce a seeded Monte Carlo run and verify worsening stress scenarios do
  not reduce simulated default counts
- load policy analytics
- export a CSV sample
- reset the static demo portfolio

## GitHub Actions CI

The CI workflow is defined in:

```text
.github/workflows/ci.yml
```

It runs on pushes and pull requests to `main` and checks:

- Python dependency installation
- full test suite
- Python syntax compilation
- research smoke test
- regional decision smoke test
- frontend JavaScript syntax
- static demo smoke test

## Deployment Gate

The GitHub Pages workflow is defined in:

```text
.github/workflows/pages.yml
```

It deploys only the static `apps/web/` demo. No real borrower data, SQLite
database, trained model artifacts, or backend secrets are deployed.
