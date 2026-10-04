# Demo Video Script

This script supports a two-minute portfolio overview and a five-minute technical
defense. Keep the recording calm, direct, and honest: MicroScore is a
research-backed product prototype, not a deployed lending system.

## Recording Setup

- Use `showcase.html?autoplay=1` for the polished two-minute narrative. Use
  `showcase.html?mode=technical&guide=1` to rehearse the five-minute technical
  defense. Close Presenter Guide before recording a clean autoplay pass.
- Close unrelated browser tabs before recording. Admissions reviewers do not
  need to meet your entire tab ecosystem.
- Record at 1920×1080 or 1440×900. The presentation is deterministic, uses no
  private data, and pauses automatically if the browser tab loses visibility.
- Use the demo accounts only:

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
staff/admin MFA code: 246810
```

- Do not enter real borrower names, IINs, phone numbers, addresses, bank
  records, or private financial data.

## Presentation Mode Voiceover

The public overview route is:

```text
https://alex-tereshkovv.github.io/micro-score/showcase.html?autoplay=1
```

Each scene lasts 17 seconds. Use the arrow keys to retake a scene, Space to
pause or resume, `G` to open Presenter Guide, Home/End to jump, and Escape to
return to the case study.

### 0:00 - 0:17 — The problem

MicroScore is an interpretable alternative credit-risk scoring prototype for
thin-file borrowers in Pavlodar, Kazakhstan. The problem is that many people can
be rejected because they lack formal credit history, even when their behavior may
show repayment discipline.

The screen shows the complete intake-to-policy system and the synthetic-data
boundary from the first frame.

### 0:17 - 0:34 — Research changed the product

The current Pavlodar borrower-level data is synthetic, so I do not claim that
this model is ready for real lending. One important finding is that
`late_payment_count` is a strong proxy feature, so the product treats the model
as decision support rather than automated approval.

Point to the `0.830 → 0.492` ablation result and the separate `0.775` public
benchmark. The conclusion is architectural: use the score for review support,
not automatic approval.

### 0:34 - 0:51 — Product workflow

Show the synthetic application queue, the local explanation, the model version,
and the review checklist. The important result is traceability: context appears
before the analyst acts.

### 0:51 - 1:08 — Monte Carlo uncertainty

Explain that the seeded baseline, adverse, and severe scenarios operate at the
portfolio-policy level. They do not change borrower scores and are scenario
planning rather than validated forecasts.

### 1:08 - 1:25 — Systems engineering

Connect the browser product, typed FastAPI contracts, repository layer, and
evidence trail. Mention tenant scoping, secret-safe audit surfaces, terminal
decision guards, and the complete 52-method PostgreSQL repository adapter.

### 1:25 - 1:42 — Responsible-use boundary

State the three claims the project does not make: automatic credit decisions,
local predictive validity, or production readiness. The next responsible step
is privacy-safe validation with local experts or an MFI partner.

### 1:42 - 1:59 — Evidence and close

End on the evidence: 142 Python tests, a reproducible ten-page engineering
report, a public synthetic-data demo, and the inspected source repository.

Closing line: “MicroScore is not a claim that a model should decide who receives
credit. It is an engineering argument that high-impact models should live inside
systems that make evidence, uncertainty, and human responsibility visible.”

## Five-Minute Technical Defense

Open:

```text
https://alex-tereshkovv.github.io/micro-score/showcase.html?mode=technical&guide=1
```

Technical mode allocates 40 seconds per scene. Presenter Guide contains the
core argument, the most likely follow-up question, a compact answer, and a link
to the corresponding evidence. Rehearse until the guide is unnecessary.

1. **Problem and scope:** explain thin-file lending, why this is a systems
   problem, and why synthetic data limits the claim.
2. **Research decision:** define ROC-AUC, explain the `0.830 → 0.492` ablation,
   discuss `late_payment_count`, and justify Logistic Regression as the
   explanation baseline rather than a causal model.
3. **Product workflow:** trace intake → score packet → explanation →
   affordability checks → human decision → append-only history.
4. **Monte Carlo:** distinguish borrower scoring from seeded portfolio-policy
   stress, explain shared and residual shocks, and reject a forecasting or VaR
   interpretation.
5. **Architecture:** connect browser, typed FastAPI contracts, repository layer,
   model registry, audit events, tenant scope, and terminal state guards.
6. **Boundary:** state what remains blocked before a real pilot: consented data,
   external and temporal validation, calibration, privacy/legal review,
   production identity, delivery, monitoring, and appeals.
7. **Close:** summarize the research finding, the architecture change it caused,
   and the next validation step. End on evidence and judgment, not feature count.

## Caption Summary

Use these short captions if the video platform allows chapter markers:

- Problem: thin-file borrowers in Pavlodar
- Caution: synthetic data, not real lending validation
- Borrower: application with behavioral signals
- MFI: score, explanation, review packet
- Governance: proxy risk, audit trail, human decision
- Uncertainty: seeded portfolio stress ranges, not forecasts
- Next: benchmark validation and pilot readiness

## Export Settings

- Duration: 90-130 seconds
- Resolution: 1080p if possible
- Audio: clear voiceover, no background music needed
- Filename: `microscore-demo-video.mp4`

## What Not To Say

- Do not say the model is ready for real loan approval; it is not ready for real loan approval.
- Do not imply synthetic Pavlodar data proves real repayment prediction.
- Do not describe the score as a legal credit decision.
- Do not describe Monte Carlo ranges as regulatory VaR or validated loss forecasts.
- Do not say the project already has MFI pilot validation unless that becomes
  true later.
