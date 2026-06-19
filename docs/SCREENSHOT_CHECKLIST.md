# Screenshot Checklist

Use this checklist when preparing README images, a portfolio page, or a demo
video thumbnail. Screenshots should show the product clearly and avoid real
personal data.

## Folder

Recommended location:

```text
docs/assets/screenshots/
```

Suggested filenames:

```text
01-login-reviewer-snapshot.png
02-borrower-application-consent.png
03-mfi-portfolio-queue.png
04-score-detail-model-use-notice.png
05-review-packet-governance.png
06-policy-lab-decision-audit.png
07-monte-carlo-stress-range.png
08-admin-audit-trail.png
```

## Required Screenshots

### 1. Login / Reviewer Snapshot

Capture the first screen with the logo, role cards, reviewer snapshot, and demo
framing visible.

Why it matters: a reviewer should understand the project in the first few
seconds.

### 2. Borrower Application + Consent

Capture the borrower form after clicking `Fill demo`, with the synthetic-data
consent checkbox visible.

Why it matters: the product shows privacy caution before collecting any borrower
application data.

### 3. MFI Portfolio + Queue

Capture the MFI analyst workspace with the application queue and portfolio
overview visible.

Why it matters: this shows the project is more than a single prediction form.

### 4. Score Detail + Model-Use Notice

Capture score detail with probability, proxy sensitivity, scenario comparison,
local explanation, and the model-use notice.

Why it matters: the central claim is interpretable decision support, not blind
automation.

### 5. Review Packet + Governance

Capture the review packet with governance flags, checklist, top factors, and
timeline.

Why it matters: this is the strongest human-in-the-loop artifact in the demo.

### 6. Policy Lab + Decision Audit

Capture approval strategy cards and decision audit rows.

Why it matters: this shows the inclusion-vs-risk trade-off and starts pointing
toward game theory and incentives later.

### 7. Monte Carlo Stress Range

Run the same policy across baseline, adverse, and severe scenarios. Capture the
scenario cards with median result, 5-95% range, loss probability, defaults,
exposure, seed, and assumptions visible.

Why it matters: this shows that MicroScore treats portfolio outcomes as ranges
under explicit assumptions rather than pretending one expected value is certain.

### 8. Admin Audit Trail

Capture the admin audit trail after a borrower submission, score, and MFI
decision.

Why it matters: auditability is critical for any responsible credit-risk system.

## Quality Bar

- Use the static demo or seeded local demo only.
- No real borrower data should appear in screenshots.
- Hide unrelated browser tabs and bookmarks if they distract.
- Keep browser zoom at 90-100%.
- Make sure no real borrower data, phone numbers, IINs, addresses, or private
  financial records are visible.
- Prefer full-width desktop screenshots for README assets.
- Retake screenshots if text overlaps, loading states are stuck, or the logo is
  cropped. Tiny visual bugs have a talent for looking much larger in admissions
  screenshots.

## README Placement

When screenshots are ready, add only 2-3 images to the README:

1. Login / reviewer snapshot.
2. MFI score detail or review packet.
3. Monte Carlo Lab, Policy Lab, or audit trail.

Keep the rest in this folder or a portfolio page so the README stays fast to
scan.
