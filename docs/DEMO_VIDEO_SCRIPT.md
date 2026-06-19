# Demo Video Script

This script is for a two-minute admissions or portfolio demo video. Keep the
recording calm, direct, and honest: MicroScore is a research-backed product
prototype, not a deployed lending system.

## Recording Setup

- Use the static demo URL when possible.
- Close unrelated browser tabs before recording. Admissions reviewers do not
  need to meet your entire tab ecosystem.
- Use the demo accounts only:

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
```

- Do not enter real borrower names, IINs, phone numbers, addresses, bank
  records, or private financial data.

## Voiceover Script

### 0:00 - 0:15 Opening

MicroScore is an interpretable alternative credit-risk scoring prototype for
thin-file borrowers in Pavlodar, Kazakhstan. The problem is that many people can
be rejected because they lack formal credit history, even when their behavior may
show repayment discipline.

Show:

- login screen
- reviewer snapshot
- synthetic-data/demo framing

### 0:15 - 0:35 Research Caution

The current Pavlodar borrower-level data is synthetic, so I do not claim that
this model is ready for real lending. One important finding is that
`late_payment_count` is a strong proxy feature, so the product treats the model
as decision support rather than automated approval.

Show:

- reviewer snapshot
- model-use language if already signed in

### 0:35 - 0:55 Borrower Flow

Sign in as the borrower. Show that a borrower can submit an application with
behavioral and regional signals. Point to the consent checkbox: the demo is for
synthetic or self-entered test data only.

Show:

- borrower workspace
- Fill demo
- synthetic-data consent
- submitted application status

### 0:55 - 1:25 MFI Analyst Flow

Sign in as the MFI analyst. Show the application queue, portfolio overview,
score detail, scenario comparison, local explanation, and review packet. The key
point is not just prediction; the system makes uncertainty, proxy risk, and
human review visible.

Show:

- MFI queue
- portfolio overview
- score detail
- model-use notice
- review packet
- decision form
- Monte Carlo baseline/adverse/severe cards

### 1:25 - 1:45 Uncertainty + Governance

Run a seeded Monte Carlo comparison and explain that the ranges come from
explicit stress and financial assumptions; they do not change borrower scores
and are not forecasts. Show the review packet and decision audit. Explain that
MicroScore records model context, assumptions, analyst decisions, governance
flags, and timeline events so that the system can be audited rather than
treated as a black box.

Show:

- governance flags
- checklist
- timeline
- decision audit
- Monte Carlo result range and loss probability

### 1:45 - 2:00 Close

End with the limitation and next step: the static demo uses synthetic data only.
The next research phase is stronger benchmark evaluation, calibration, fairness
analysis, and eventually privacy-safe validation with local experts or an MFI.

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
