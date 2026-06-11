# MicroScore Impact Plan

## Why Pavlodar

MicroScore focuses on Pavlodar and Pavlodar region because the project started
from a local observation: people in smaller cities and rural districts can be
rejected for credit because they lack formal credit history, official
employment, or collateral. The region also contains a useful mix of urban,
industrial, peri-urban, and rural contexts.

## Potential Beneficiaries

- Thin-file borrowers who may be responsible but lack traditional credit
  records.
- Small entrepreneurs and self-employed workers.
- Rural borrowers whose financial behavior may not be captured by bank-centric
  scoring.
- Microfinance organizations that need better risk review and portfolio
  analytics.
- Researchers studying financial inclusion and responsible credit scoring.

## Potential Harms

- A model could reject people unfairly if it treats weak digital activity as
  low trustworthiness.
- A proxy such as `late_payment_count` could recreate traditional exclusion.
- A poorly calibrated score could mislead loan officers.
- Borrowers could be encouraged to perform superficial behaviors that improve a
  score but not financial health.
- Sensitive data collection could harm privacy and trust.

## Stakeholder Feedback Log

Use `docs/STAKEHOLDER_INTERVIEW_GUIDE.md` for consent-based interview prompts
and `docs/VALIDATION_TRACKER.md` to track which project claims have local
evidence.

| Date | Stakeholder | Feedback | Project response |
| --- | --- | --- | --- |
| Pending | Local borrower | Not yet interviewed | Prepare consent-based interview questions. |
| Pending | MFI loan officer | Not yet interviewed | Prepare workflow review and score-explanation questions. |
| Pending | Data/privacy reviewer | Not yet reviewed | Prepare data statement and model card for critique. |

## Interview Questions To Start With

The full interview protocol is in `docs/STAKEHOLDER_INTERVIEW_GUIDE.md`. The
short starter questions are:

Borrowers:

- What makes it difficult to get a loan in your area?
- Which financial behaviors would you consider fair to share with an MFI?
- Which data would feel too private or unsafe to share?
- Would a small starter loan with transparent rules feel useful?

MFI analysts:

- Which signals do you trust when a borrower has little credit history?
- What makes a score explanation useful or useless?
- When would you override a model recommendation?
- Which segment analytics would help portfolio risk review?

## What Has Changed Because Of Risk Review

- `customer_id`, `credit_score`, `loan_default_history`, and `fraud_flag` are
  dropped as leakage or target-like variables.
- `late_payment_count` is treated as a proxy risk, not just a strong feature.
- The API includes a thin-file scenario without `late_payment_count`.
- The product returns decision-support recommendations instead of automatic
  approvals or declines.
- Regional indices are documented as assumptions when evidence is missing.

## Future Pilot Plan

1. Interview local borrowers and at least one MFI analyst.
2. Replace regional assumptions with official and measured local indicators.
3. Seek anonymized, consent-compliant pilot data.
4. Validate calibration and error rates before any operational use.
5. Add a manual appeal/review mechanism.
6. Publish a short demo video and a non-technical walkthrough.

## Impact Claim Status

MicroScore currently has a strong social motivation and a working prototype,
but it does not yet prove real-world impact. The impact claim will become
stronger only after stakeholder interviews, real-data validation, and a pilot
review with an MFI or financial-inclusion expert.
