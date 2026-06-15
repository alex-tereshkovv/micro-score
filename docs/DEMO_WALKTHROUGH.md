# Demo Walkthrough

This walkthrough is for a two-minute admissions or portfolio review demo. It is
designed for the static public demo, but the same flow also works with the local
FastAPI prototype.

## Demo URL

Local static demo:

```text
http://127.0.0.1:5173?demo=static
```

Planned public demo:

```text
https://alex-tereshkovv.github.io/micro-score/
```

## Demo Accounts

```text
borrower@test.com
analyst@test.com
admin@test.com
password: password123
```

## Two-Minute Script

### 0:00 - 0:15 Problem

MicroScore studies alternative credit-risk scoring for thin-file borrowers in
Pavlodar, Kazakhstan. The problem is that people can be rejected because they
have no formal credit history, even when their behavior may show repayment
discipline.

On the login screen, point to the reviewer snapshot: the demo is a research and
product prototype, uses synthetic Pavlodar data, and is designed for human
decision support rather than automated approval.

### 0:15 - 0:35 Research Caution

The current Pavlodar borrower-level dataset is synthetic. The project does not
claim real lending validation. A key research finding is that `late_payment_count`
dominates the synthetic model, so the model is treated as a decision-support
prototype, not an automated approval system.

### 0:35 - 0:55 Borrower Flow

Sign in as:

```text
borrower@test.com
```

Show the borrower workspace, fill the demo application, and submit it. The
borrower confirms that only synthetic or self-entered test data is being used.
The important point is that a thin-file borrower can submit behavioral and
regional signals without collateral-based assumptions, while the demo explicitly
warns against entering real personal data.

### 0:55 - 1:30 MFI Analyst Flow

Sign in as:

```text
analyst@test.com
```

Show the application queue, portfolio overview, score detail, scenario
comparison, local explanation, review packet, and decision form. Point out the
model-use notice in score detail: the score is decision support, proxy-sensitive
cases require manual review, and a human analyst records the decision.

### 1:30 - 1:45 Governance

Open the review packet and point to governance flags, the checklist, the
timeline, proxy sensitivity, and decision audit. This is where MicroScore is
more than a raw classifier: it makes model limitations visible.

### 1:45 - 2:00 Next Step

End by explaining that the static demo uses synthetic data only. The next
research step is local validation with expert feedback and, later, pilot data
from an MFI under privacy-safe conditions.

## What Not To Claim

- Do not say the model is ready for real loan approval.
- Do not imply synthetic Pavlodar data proves repayment prediction.
- Do not collect or enter real borrower data in the public demo.
- Do not present the score as a legal credit decision; it is not a legal credit decision.

## Short Reviewer Summary

MicroScore is an interpretable, human-in-the-loop credit-risk research prototype
for thin-file borrowers. Its strongest current contribution is not accuracy
alone, but the combination of behavioral scoring, proxy-risk analysis,
review-packet governance, and a working product flow.
