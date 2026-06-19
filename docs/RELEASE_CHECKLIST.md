# Release Checklist

Use this checklist before pushing a portfolio/public-demo release.

## Code Quality

- Run the local release gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

- Full test suite passes:

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

- JavaScript syntax passes:

```powershell
node --check apps\web\app.js
node --check apps\web\mock-api.js
node --check scripts\static-demo-smoke.js
```

- Static demo smoke test passes:

```powershell
node scripts\static-demo-smoke.js
```

- Git diff has no whitespace errors:

```powershell
git diff --check
```

## Demo Safety

- Static demo warning is visible.
- Borrower submission requires the synthetic-data consent checkbox.
- MFI score detail and review packet show the model-use notice.
- Admin model registry shows exactly one active version.
- Activating a candidate marks older review packets as stale until re-scored.
- Monte Carlo output says scenario planning, not forecast or borrower score.
- Repeating a run with the same seed produces identical scenario distributions.
- Adverse/severe defaults do not improve relative to baseline for paired draws.
- Demo accounts use synthetic data only.
- No real borrower names, phone numbers, IINs, addresses, or bank records are
  present.
- README clearly states that synthetic data is not real-world lending
  validation.

## Public Demo

- GitHub Pages source is set to **GitHub Actions**.
- `Deploy static web demo` workflow succeeds.
- Public demo opens without FastAPI.
- Hosted page automatically uses static demo mode.
- Hosted/static demo hides local API settings from the reviewer-facing sidebar.
- `Reset demo` restores the synthetic portfolio.
- MFI queue, score detail, review packet, and analytics show clear loading,
  empty, and error states.

## Reviewer Assets

- Login screen reviewer snapshot is visible and current.
- README Snapshot is current.
- Demo Walkthrough is current.
- Demo Video Script is current.
- Screenshot Checklist is current.
- Public Demo Plan is current.
- Model Card and Data Statement still match the implementation.
- Research Paper draft mentions the latest limitations and findings.

## Final Manual Check

Open the public or local static demo and verify:

1. Login page is the first visible screen.
2. Borrower can submit a demo application.
3. MFI analyst can view queue, score detail, review packet, and analytics.
4. Admin can view audit trail and clear/reset demo state.
5. No screen invites users to submit real personal data.
6. Screenshots and demo video use only synthetic/demo data.
