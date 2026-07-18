# Pilot Evidence Claims Audit v1

This artifact defines what MicroScore may and may not claim during pilot
readiness discussions. It is a research guardrail, not a product-behavior
change.

## Claim Classes

| Class | Meaning | Allowed wording | Prohibited wording |
| --- | --- | --- | --- |
| Implemented evidence | Functionality exists in code, tests, docs, or generated artifacts. | "Implemented in the prototype and covered by tests/artifacts." | "Production-ready" or "validated for real borrowers." |
| Synthetic-only evidence | Finding comes from synthetic borrower-level data or static demo data. | "Evidence in synthetic data." | "Evidence of real-world MFI performance." |
| Public benchmark evidence | Finding comes from a public non-Kazakhstan credit dataset. | "Pipeline benchmark on public credit-risk data." | "Validated for Pavlodar or Kazakhstan MFI lending." |
| Assumption scaffold | Transparent scenario, regional, KZT, or Monte Carlo assumption. | "Scenario assumption pending validation." | "Forecast", "KZT profit", "regulatory capital", or "pricing guidance." |
| Blocked real-world validation | Claim requires consented local data or partner review before use. | "Not yet validated; requires pilot evidence." | "Ready for operational lending." |

## Current Evidence Matrix

| Topic | Current status | What can be claimed | What cannot be claimed yet |
| --- | --- | --- | --- |
| Scoring workflow | Implemented evidence | The prototype can score synthetic applications and preserve model-version provenance. | The score is a legal credit decision or production lending model. |
| Review Readiness / Action Plan | Implemented evidence | The UI can summarize review packet readiness for a human analyst. | Readiness means approve, decline, affordability verdict, or regulatory compliance. |
| `late_payment_count` proxy risk | Synthetic-only evidence | Synthetic experiments show strong dependence on a repayment-history proxy. | The same magnitude holds on real MFI data. |
| Proxy Monitoring v2 | Implemented evidence | Research artifacts track repayment-history, monetary-scale, affordability, debt/formal-credit, and digital-access proxy families. | Monitoring automatically removes features or changes borrower outcomes. |
| KZT calibration | Assumption scaffold | Monetary outputs are prototype amount units and KZT evidence requirements are documented. | Demo outputs are calibrated KZT, expected KZT profit, validated loss, or pricing guidance. |
| Monte Carlo Policy Lab | Assumption scaffold | Seeded simulations show scenario ranges under supplied assumptions. | Results are repayment forecasts, regulatory VaR, capital estimates, or proof a policy is safe. |
| UCI public benchmark | Public benchmark evidence | The modeling pipeline runs on a real public credit-risk benchmark. | The benchmark validates Pavlodar geography, local borrowers, or Kazakhstan MFI deployment. |
| Pilot readiness | Blocked real-world validation | The repo documents data, consent, calibration, proxy, and human-review requirements for a future pilot. | MicroScore is ready to use real borrower data or make operational lending decisions. |

## Evidence Required Before Stronger Pilot Claims

Before MicroScore can make real-world or KZT-denominated pilot claims, it needs:

1. a written data-use agreement and consent boundary;
2. anonymized or pseudonymized local application records;
3. verified KZT principal, income, debt, tenor, fees, repayment schedules, and
   repayment outcomes;
4. documented margin, LGD, operating cost, funding cost, review-conversion, and
   stress assumptions from an MFI or accepted public source;
5. held-out calibration review on local outcomes;
6. proxy monitoring review, especially for `late_payment_count` and
   monetary/digital-access features;
7. segment-level error, approval, and override analysis;
8. documented human analyst decision and appeal process.

## Required Reviewer Language

Use:

- "research prototype";
- "decision-support only";
- "synthetic-data evidence";
- "public benchmark evidence";
- "prototype amount units";
- "scenario planning, not forecast";
- "not a legal credit decision";
- "blocked pending consented local validation data."

Do not use:

- "validated pilot model";
- "real KZT profit";
- "real portfolio forecast";
- "automatic lending policy";
- "regulatory VaR";
- "production affordability verdict";
- "validated financial inclusion impact";
- "ready for real borrower decisions."

## Product Boundary

This audit does not change scoring, API responses, Review Readiness semantics,
policy thresholds, borrower lifecycle, or frontend behavior. It only limits how
research and product workstreams should describe evidence until real permitted
validation data exists.
