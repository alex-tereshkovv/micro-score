# MicroScore Project Brief

MicroScore is an interpretable alternative credit-risk research and
decision-support prototype for thin-file borrowers in Pavlodar, Kazakhstan. It
connects reproducible modeling, responsible-ML documentation, and a working
product demo for reviewing risk, explanations, and policy trade-offs.

## One-Minute Snapshot

| Question | Answer |
| --- | --- |
| What is it? | A credit-risk decision-support prototype for underserved borrowers. |
| Who is it for? | Borrowers with limited formal credit history and regional MFIs. |
| Current product | Public static web demo plus local FastAPI/SQLite prototype. |
| Current research | Synthetic Pavlodar experiment plus public UCI benchmark. |
| Main finding | The synthetic model depends too strongly on `late_payment_count`. |
| Key limitation | It is not validated on real Kazakhstan MFI borrower data. |
| Safety position | Human-in-the-loop decision support, not automatic lending. |

## Start Here

1. Three-minute case study: https://alex-tereshkovv.github.io/micro-score/#/review
2. Two- or five-minute technical walkthrough: https://alex-tereshkovv.github.io/micro-score/showcase.html
3. Engineering evidence: https://alex-tereshkovv.github.io/micro-score/evidence.html
4. Role-based demo: https://alex-tereshkovv.github.io/micro-score/
5. Research paper: [PDF](../output/pdf/MicroScore_Research_Paper.pdf) · [source](RESEARCH_PAPER.md)
6. Model governance: [MODEL_CARD.md](MODEL_CARD.md)
7. Technical interview preparation: [TECHNICAL_INTERVIEW_GUIDE.md](TECHNICAL_INTERVIEW_GUIDE.md)

Demo accounts are `borrower@test.com`, `analyst@test.com`, and
`admin@test.com`. The password is `password123`; the staff/admin MFA code is
`246810`.

The public demo uses synthetic in-browser data only. It does not collect real
borrower names, identity numbers, phone numbers, bank records, or addresses.

## What Is Implemented

- A borrower workspace for submitting synthetic loan applications.
- An analyst workspace for queue review, scoring, local explanations, policy
  analytics, and portfolio uncertainty.
- An admin workspace for audit, identity, model, and readiness review.
- A local FastAPI API with seeded users, tenant scoping, lifecycle controls,
  model provenance, and SQLite persistence.
- A research pipeline with leakage checks, ablation, calibration, error and
  segment analysis, threshold policies, and a public benchmark.
- A static GitHub Pages demo that exercises the main workflows without a local
  backend or real personal data.

## Core Research Finding

The full synthetic models reach ROC-AUC of about `0.806` for Logistic
Regression and `0.830` for Random Forest. However,
`late_payment_count` alone reaches about `0.827`; removing it reduces model
performance to approximately `0.486-0.492`.

This is not evidence that the feature is automatically invalid. It is evidence
that the synthetic dataset has too little independent thin-file signal and that
the apparent model performance is fragile. The project therefore treats this
as a proxy-risk and validation problem rather than hiding the result.

## Why This Is A System, Not Just A Model

MicroScore has three connected layers:

- Research: reproducible experiments, artifacts, and evidence boundaries.
- Product: borrower, analyst, and admin workflows backed by typed contracts.
- Public demo: browser-only synthetic data for safe, low-friction inspection.

The score is only one input. Threshold policies translate probability into
approve/review/decline zones; analysts retain responsibility; audit events,
model versions, and lifecycle rules preserve context; Monte Carlo simulation
tests portfolio-level uncertainty without changing borrower scores.

## What Not To Claim

MicroScore is not:

- a production credit-scoring model;
- a replacement for a credit bureau or an analyst;
- validated on real Pavlodar borrowers;
- an automatic approval or rejection engine;
- proof that alternative behavioral data is sufficient for lending;
- a calibrated financial forecast or regulatory risk model.

The defensible claim is narrower: MicroScore is a working research-and-product
prototype for studying how interpretable alternative data, explicit policy,
and human oversight could support regional lending decisions.

## Next Validation Milestones

1. Validate data definitions and workflow assumptions with local experts.
2. Obtain consented, privacy-reviewed pilot data or a stronger public proxy.
3. Test temporal stability, calibration, and segment performance out of sample.
4. Complete production identity, storage, deployment, and monitoring controls.
5. Re-estimate policy economics and Monte Carlo stresses from observed outcomes.

## Project Takeaway

MicroScore is strongest when its evidence boundary remains visible. The project
combines ML experimentation with API design, persistence, frontend workflows,
testing, governance, and honest negative results. Its present value is not a
claim of lending readiness; it is a reproducible demonstration of how such a
system can be examined before anyone trusts it with real decisions.
