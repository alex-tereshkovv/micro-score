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

The shared borrower intake contract has a focused Node test:

```powershell
node scripts\application-intake-smoke.js
```

It verifies accepted input plus amount boundaries, district/settlement
consistency, whole-number counts, unknown-signal rejection, and consent.

The Portfolio Dashboard v2 summary has a focused Node test:

```powershell
node scripts\portfolio-dashboard-smoke.js
```

It verifies risk-band counts, district risk ordering, top-district
concentration, settlement-type ordering, rural/peri-urban contextual share, and
static demo seed-data consistency.

The public-demo layer has its own Node smoke test:

```powershell
node scripts\static-demo-smoke.js
```

The smoke test verifies that the in-browser static backend can:

- sign in as an MFI analyst
- verify auth/session expiry metadata in the static contract
- create and accept an expiring staff invite with password-policy enforcement
- load the seeded application queue
- score an application
- open a review packet
- list borrower-safe application history and complete a guarded lifecycle from
  submission through review to a terminal decision
- switch the active model registry version and detect a stale score
- re-score with the newly active model and preserve its governance snapshot
- reproduce a seeded Monte Carlo run and verify worsening stress scenarios do
  not reduce simulated default counts
- verify simulation fingerprint stability, standard-error diagnostics, and
  stored history/detail parity
- verify Portfolio Dashboard v2 district and settlement summary rows
- load policy analytics
- export a CSV sample
- reset the static demo portfolio

The dedicated frontend workflow contract test is:

```powershell
node scripts\frontend-workflow-smoke.js
```

It exercises the static API together with the shared Risk Detail view-model:
borrower-safe history, affordability completeness, manual-review transition,
chronological decision history, and terminal-state locking.

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
- application intake contract smoke test
- portfolio dashboard smoke test
- static demo smoke test

## Deployment Gate

The GitHub Pages workflow is defined in:

```text
.github/workflows/pages.yml
```

It deploys only the static `apps/web/` demo. No real borrower data, SQLite
database, trained model artifacts, or backend secrets are deployed.
