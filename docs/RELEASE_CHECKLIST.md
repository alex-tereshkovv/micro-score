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
node --check apps\web\application-intake.js
node --check apps\web\portfolio-dashboard.js
node --check apps\web\risk-detail.js
node --check scripts\static-demo-smoke.js
node --check scripts\frontend-workflow-smoke.js
node --check scripts\application-intake-smoke.js
node --check scripts\portfolio-dashboard-smoke.js
```

- Application intake smoke test passes:

```powershell
node scripts\application-intake-smoke.js
```

- Portfolio dashboard smoke test passes:

```powershell
node scripts\portfolio-dashboard-smoke.js
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
- Invalid borrower fields are highlighted with a visible summary and are rejected
  by the same intake contract in static mode and the typed API.
- Unknown behavioral fields and district/settlement mismatches return validation
  errors instead of entering the scoring pipeline.
- Auth responses and `/me` expose `session_expires_at` and
  `session_ttl_seconds`; the session pill makes token expiry visible.
- Staff Invite v2 creates expiring analyst invites, supports admin revocation,
  enforces password setup at acceptance time, and records invite
  creation/acceptance/revocation audit events; direct temporary-password
  provisioning remains prototype-only.
- Borrower history lists only the signed-in account's applications and excludes
  internal scores, analyst identity, and review notes.
- Lifecycle transitions preserve `under_review` during re-scoring and reject
  mutations after `approved` or `declined`.
- Risk Detail loads automatically and shows lifecycle actions, affordability
  completeness, governance checks, and chronological decision history.
- Affordability output states that it is screening context, not a verdict.
- MFI score detail and review packet show the model-use notice.
- Portfolio Overview shows risk bands, district risk, settlement mix, policy
  mix, analyst decisions, and the screenshot snapshot note.
- Admin model registry shows exactly one active version.
- Activating a candidate marks older review packets as stale until re-scored.
- Monte Carlo output says scenario planning, not forecast or borrower score.
- Repeating a run with the same seed produces identical scenario distributions.
- Repeated runs preserve a stable 64-character portfolio fingerprint.
- Simulation history can reopen the exact stored result and remains tenant-scoped.
- Monte Carlo standard-error diagnostics are present and nonnegative.
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
- Portfolio dashboard charts are populated from synthetic scored applications
  and do not imply real regional calibration.

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
