# MicroScore Admissions Reviewer Brief

MicroScore is an interpretable alternative credit-risk scoring prototype for
thin-file borrowers in Pavlodar, Kazakhstan. It combines a research pipeline,
responsible-ML documentation, and a working public demo that shows how a
regional MFI analyst could review risk, explanations, and policy trade-offs.

## One-Minute Snapshot

| Question | Answer |
| --- | --- |
| What is it? | A credit-risk decision-support prototype for underserved borrowers. |
| Who is it for? | Borrowers with limited formal credit history and regional MFIs. |
| Region | Pavlodar region, Kazakhstan. |
| Current product | Public static web demo plus local FastAPI/SQLite prototype. |
| Current research | Synthetic Pavlodar experiment plus public UCI credit-risk benchmark. |
| Main finding | The synthetic model depends too strongly on `late_payment_count`. |
| Key limitation | It is not validated on real Kazakhstan MFI borrower data yet. |
| Safety position | Human-in-the-loop decision support, not automatic lending. |

## What To Open First

1. Public demo: https://alex-tereshkovv.github.io/micro-score/
2. Demo accounts: `borrower@test.com`, `analyst@test.com`, `admin@test.com`
3. Password: `password123`
4. Demo script: [DEMO_VIDEO_SCRIPT.md](DEMO_VIDEO_SCRIPT.md)
5. Research paper draft: [RESEARCH_PAPER.md](RESEARCH_PAPER.md)
6. Model governance: [MODEL_CARD.md](MODEL_CARD.md)

The public demo uses synthetic in-browser data only. It does not collect real
borrower names, identity numbers, phone numbers, bank records, or addresses.

## What Is Already Built

- Borrower workspace for submitting a synthetic loan application.
- MFI analyst workspace for queue review, score detail, explanations, and
  policy analytics.
- Admin workspace for audit-trail inspection.
- Static GitHub Pages demo for reviewers who will not run a local backend.
- Local FastAPI API with seeded demo users and SQLite persistence.
- Research pipeline with leakage checks, ablation studies, calibration review,
  fairness/segment audit, benchmark evaluation, and generated reports.
- Responsible documentation: data statement, model card, impact notes,
  validation plan, demo walkthrough, and release checklist.

## Research Findings Worth Highlighting

1. Full synthetic-data models show moderate ROC-AUC, but the result is fragile.
2. `late_payment_count` behaves like a dominant proxy feature in the synthetic
   dataset.
3. When `late_payment_count` is removed, thin-file performance falls close to
   random, which is an honest warning about the current dataset.
4. Public UCI benchmark testing shows that the pipeline can run on a real
   credit-risk dataset, but that benchmark is not Pavlodar MFI data.
5. Threshold policy analysis exposes a real conflict between lender protection
   and borrower inclusion.

## Why This Is Not Just A Notebook

MicroScore has three connected layers:

- Research layer: reproducible experiments and governance documents.
- Product layer: role-based borrower, MFI analyst, and admin workflows.
- Public-demo layer: a reviewer-friendly static demo that does not require
  PowerShell, Python setup, or local ports.

That matters because financial-inclusion ML is not only about accuracy. A
serious lending tool must explain its decisions, disclose its limitations,
protect privacy, and remain usable by non-technical stakeholders.

## What Not To Claim

MicroScore should not be presented as:

- a production credit-scoring model;
- a replacement for credit bureaus;
- a system validated on real Pavlodar borrowers;
- an automatic approval or rejection engine;
- proof that behavioral data is enough for lending decisions.

The stronger claim is narrower and more honest: MicroScore is a working
research-and-product prototype for studying how alternative data, local
context, and human oversight could support fairer regional lending.

## Five-Month Direction

The next milestone is to move from a strong prototype toward pilot readiness:

1. Improve the public web experience and record a two-minute demo video.
2. Add a cleaner deployed API or a hosted simplified demo path.
3. Expand public benchmark evaluation and compare failure modes.
4. Validate Pavlodar assumptions with official sources and expert feedback.
5. Use the [pilot data schema](PILOT_DATA_SCHEMA.md) to avoid sensitive
   unnecessary data.
6. Replace synthetic assumptions with validated local signals where possible.

## Reviewer Takeaway

MicroScore is strongest when it is read as a responsible research prototype:
ambitious about financial inclusion, technically reproducible, honest about
synthetic data, and already shaped like a real product that could be piloted
with careful governance.
