# Public Demo Plan

MicroScore is currently a local FastAPI + static web prototype with a static
frontend demo mode. The repository now includes a GitHub Pages workflow for the
static demo. The next step is to enable GitHub Pages in the repository settings
and publish the public URL.

## Goal

Provide a lightweight public demo that shows the core idea in under two
minutes:

- borrower submits a sample application
- MFI analyst sees a scored queue
- analyst opens a review packet
- analyst records a decision
- dashboard shows district risk, settlement mix, portfolio analytics, and
  decision audit

The public demo must clearly state that it uses demo or synthetic data and is
not a lending service.

## Recommended First Demo

Start with a static or simplified demo before deploying the full backend.

### Option A: GitHub Pages Static Demo

Best first step because it is simple and stable.

- Status: local static demo mode implemented with `apps/web/mock-api.js`.
- Deployment workflow: `.github/workflows/pages.yml`.
- Setup instructions: `docs/STATIC_DEMO_DEPLOYMENT.md`.
- Use synthetic in-browser demo data.
- Host only the frontend interaction on GitHub Pages or Vercel.
- Label accounts as demo personas and keep the synthetic-data warning visible.
- Show Portfolio Dashboard v2, review packet, decision audit, and CSV export
  sample.

Trade-off: not a real backend, but very easy for a reviewer to open.

### Option B: Streamlit or Hugging Face Spaces

Good for a research-facing demo.

- Load a small demo dataset.
- Let users change applicant features.
- Show probability, top factors, thin-file scenario, and decision support.
- Include benchmark comparison once public benchmark work is implemented.

Trade-off: less like the final product, but stronger for research review.

### Option C: Hosted FastAPI + Static Frontend

Best later option.

- Frontend on Vercel, Netlify, or GitHub Pages.
- API on Render, Railway, Fly.io, or another hosted service.
- Use a seeded demo database only.
- Add rate limits and stronger session handling before any real data.

Trade-off: closest to product, but more deployment/security work.

## Reviewer Asset Checklist

- Live Demo: static mode implemented locally; GitHub Pages workflow ready
- Demo Video: planned
- Demo walkthrough: `docs/DEMO_WALKTHROUGH.md`
- Demo video script: `docs/DEMO_VIDEO_SCRIPT.md`
- Screenshot checklist: `docs/SCREENSHOT_CHECKLIST.md`
- Release checklist: `docs/RELEASE_CHECKLIST.md`
- Research Paper PDF: planned
- GitHub README: should stay short and link to detailed docs
- Demo data: synthetic/demo only
- Privacy note: no real borrower data

## Two-Minute Video Outline

1. Problem: thin-file borrowers in Pavlodar can be excluded by traditional
   credit history requirements.
2. Research finding: synthetic-data model is fragile because `late_payment_count`
   dominates.
3. Product flow: borrower application, MFI review queue, Portfolio Dashboard
   v2, score detail, review packet, human decision.
4. Governance: proxy warning, timeline, audit trail, decision analytics.
5. Limitation and next step: public benchmark validation and eventual local
   pilot data.

## Non-Goals

- Do not present the demo as a real lending product.
- Do not collect real borrower personal data.
- Do not imply that synthetic results validate real-world credit decisions.
