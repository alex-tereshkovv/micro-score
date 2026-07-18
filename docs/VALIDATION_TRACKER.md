# MicroScore Validation Tracker

This tracker separates what MicroScore has already demonstrated from what still
needs local evidence, expert feedback, or real pilot data.

## Current Validation Status

| Claim or assumption | Current evidence | Status | Next validation action |
| --- | --- | --- | --- |
| Thin-file borrowers can be excluded by traditional credit checks | Project motivation and local observation | Needs stakeholder evidence | Interview borrowers about rejection reasons and missing credit history. |
| Synthetic model performance depends heavily on `late_payment_count` | Ablation study and feature importance reports | Evidence in synthetic data | Keep as a research finding, not a real-world claim. |
| Adjacent monetary, affordability, debt, and digital-access features may act as proxies | Proxy Monitoring v2 research artifact | Evidence in synthetic data | Review `proxy_monitoring.csv` before KZT, thin-file, fairness, or pilot claims. |
| Behavioral-only signals are weak in the current synthetic dataset | Ablation study | Evidence in synthetic data | Identify real behavioral signals that are fair and measurable. |
| Pavlodar regional layer is useful for local analysis | Regional scaffold and dashboard segmentation | Assumption scaffold | Replace assumptions with official public indicators where possible. |
| District-level context may reveal access gaps | Simulated regional features | Hypothesis | Validate with public statistics and stakeholder feedback. |
| MFI analysts need explainable score outputs | Product assumption | Needs expert feedback | Interview at least one lender, finance worker, or fintech reviewer. |
| Borrowers need human review and appeal options | Ethical design assumption | Needs borrower feedback | Ask borrowers what would feel fair after a high-risk score. |
| Policy Lab can help show inclusion-vs-risk trade-offs | Working product prototype | Prototype evidence | Ask reviewers whether approve/review/decline analytics are understandable. |
| Monte Carlo ranges help analysts reason about portfolio uncertainty | Seeded baseline/adverse/severe prototype with explicit assumptions | Methodological prototype only | Validate margin, LGD, review conversion, operating cost, calibration volatility, and stress shifts with an MFI before pilot use. |
| Monetary outputs can be interpreted as KZT | KZT assumptions pack documents prototype amount units | Not validated | Collect consented local principal, income, debt, tenor, margin, LGD, cost, and repayment outcomes before KZT-denominated claims. |
| Pilot evidence claims are easy to overstate | `docs/PILOT_EVIDENCE_CLAIMS.md` claim matrix | Implemented evidence guardrail | Keep reviewer language within implemented, synthetic-only, benchmark, assumption, or blocked-validation categories. |
| The model is not ready for operational lending | Data statement, model card, synthetic-data limitation | Validated by project constraints | Keep this limitation visible in README, paper, and demo. |

## Validation Milestones

### Milestone 1: Local Feedback Batch

Target:

- 3 borrower interviews;
- 1 MFI, finance, or fintech reviewer;
- 1 privacy, data, or ethics reviewer.

Output:

- summarized notes in a private file;
- non-sensitive themes added to `docs/IMPACT.md`;
- updates to product requirements and data statement.

### Milestone 2: Public Evidence Refresh

Target:

- official population and urban/rural data for Pavlodar region;
- public ICT or internet-access indicators;
- public labor/income indicators;
- financial-sector or MFI context from official/regulatory sources.

Output:

- updated `docs/DATA_STATEMENT.md`;
- evidence table with source, feature relevance, and limitation;
- clear labels for evidence-based vs assumption fields.

### Milestone 3: Reviewer Demo

Target:

- one-click or near-one-click demo;
- 20-application demo portfolio;
- portfolio overview and policy lab;
- two-minute walkthrough script.

Output:

- public or reviewer-safe demo link;
- screenshots in README;
- video walkthrough.

### Milestone 4: Pilot Data Readiness

Target:

- written list of required anonymized fields;
- privacy and consent boundaries;
- pilot data-use agreement outline;
- model validation plan for calibration, fairness, and error analysis.
- KZT calibration assumptions and proxy-monitoring review.

Output:

- pilot appendix in the research paper;
- updated model card;
- evidence-claims audit review;
- decision not to use real data until governance is clear.

## Interview Evidence Acceptance Criteria

An interview observation can be added to project docs only if:

- it is paraphrased, not a private quote with identifying details;
- it does not include personal financial records;
- it is linked to a project decision or hypothesis;
- it is labeled as qualitative evidence, not statistical proof.

## Public Evidence Acceptance Criteria

A public source can support a regional feature only if:

- the source is official or clearly secondary;
- the date or publication period is recorded;
- the geographic level is clear;
- the source supports the feature directly, or the assumption is labeled;
- limitations are written next to the feature.

## Product Validation Questions

Use these questions when showing the prototype:

1. Can a reviewer understand the borrower queue without explanation?
2. Can an analyst see why a specific application is risky?
3. Does the Policy Lab make the trade-off between access and risk clear?
4. Does the Portfolio Overview reveal useful regional or segment patterns?
5. Are warnings about synthetic data and proxy risk visible enough?
6. What is confusing, missing, or misleading?

## Next Three Concrete Actions

1. Run 3 short borrower interviews using `docs/STAKEHOLDER_INTERVIEW_GUIDE.md`.
2. Review `docs/KZT_CALIBRATION_ASSUMPTIONS.md` with an MFI or finance reviewer.
3. Add non-sensitive summarized findings to `docs/IMPACT.md`.
