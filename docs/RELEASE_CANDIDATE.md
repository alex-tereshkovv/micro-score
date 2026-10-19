# Release Candidate Freeze v1

MicroScore entered a reviewer-ready release-candidate phase on 2026-10-19.
This freeze prioritizes evidence consistency, reproducibility, and explainable
ownership over additional product features.

## Frozen Reviewer Story

The release candidate makes one narrow claim: MicroScore is a working research
and decision-support prototype that connects interpretable modeling, human
review, portfolio uncertainty, auditability, and explicit pre-pilot blockers.

It does not claim that the model is validated for Kazakhstan lending, that the
public benchmark is local validation, or that synthetic operating/performance
results establish production readiness.

## Canonical Entry Points

1. Engineering case study: `https://alex-tereshkovv.github.io/micro-score/#/review`
2. Technical walkthrough: `https://alex-tereshkovv.github.io/micro-score/showcase.html`
3. Evidence hub: `https://alex-tereshkovv.github.io/micro-score/evidence.html`
4. Short project overview: `docs/PROJECT_BRIEF.md`
5. Research paper: `output/pdf/MicroScore_Research_Paper.pdf`
6. Engineering case study: `output/pdf/MicroScore_Engineering_Case_Study.pdf`
7. Technical defense guide: `docs/TECHNICAL_INTERVIEW_GUIDE.md`

## Submission Manifest

`reports/submission/manifest.json` is the deterministic evidence index. It
records the release label, synchronized quality counts, headline metrics,
required limitations, reproduction commands, and SHA-256 hashes for critical
documents, PDFs, public pages, research artifacts, tests, and release scripts.
UTF-8 text is normalized to LF before hashing so the manifest is identical on
Windows and Linux; binary artifacts such as PDFs are hashed byte-for-byte.
The hashed set also includes the deterministic technical-defense packet, whose
five headline claims are checked directly against generated CSV evidence.

Build it only after release artifacts are final:

```powershell
.venv\Scripts\python scripts\build-submission-manifest.py --write
```

Verify that no listed artifact has drifted:

```powershell
.venv\Scripts\python scripts\build-submission-manifest.py --check
```

The committed manifest is not a signature or provenance authority. It is a
repository consistency control; Git history and CI remain the audit trail.

## Freeze Gate

A release candidate is blocked when any of these conditions is true:

- README, public pages, PDFs, or evidence scripts disagree on test/smoke counts;
- the research paper's numbered findings are duplicated or out of sequence;
- a reviewer-facing artifact revives the deprecated reviewer-specific filename;
- a headline metric is missing its synthetic/public-benchmark evidence boundary;
- the technical-defense packet is stale, loses one of its 12 core questions, or
  disagrees with the generated research metrics;
- a critical artifact is missing or its committed hash is stale;
- either PDF is unreadable, unexpectedly short, or missing its central finding
  and limitation;
- the complete release gate or one of the four independent CI jobs fails.

## Current Evidence Boundary

| State | Release-candidate position |
| --- | --- |
| Public review | Ready with synthetic browser data. |
| Local/container demonstration | Ready with seeded synthetic data. |
| Research reproducibility | Covered by generated artifacts and tests. |
| PostgreSQL engineering path | Exercised in disposable CI and containers. |
| Real borrower data | Blocked. |
| Production lending decision | Blocked. |
| Managed identity, monitoring, and operations | Incomplete. |

## Change Policy During Freeze

Allowed changes are evidence corrections, accessibility/usability fixes,
security fixes, test stabilization, and documentation clarification. New product
features should be deferred unless they close a release-blocking defect. Any
allowed change must rebuild the affected PDF/artifact, regenerate the manifest,
and pass the complete release gate before publication.
