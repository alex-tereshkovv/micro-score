# Public Demo Plan

MicroScore is currently a local FastAPI + static web prototype. For admissions
and portfolio review, the project needs a clickable public demo that can be
opened without cloning the repository.

## Goal

Provide a lightweight public demo that shows the core idea in under two
minutes:

- borrower submits a sample application
- MFI analyst sees a scored queue
- analyst opens a review packet
- analyst records a decision
- dashboard shows portfolio analytics and decision audit

The public demo must clearly state that it uses demo or synthetic data and is
not a lending service.

## Recommended First Demo

Start with a static or simplified demo before deploying the full backend.

### Option A: GitHub Pages Static Demo

Best first step because it is simple and stable.

- Use mocked JSON data exported from the local demo database.
- Host only the frontend interaction on GitHub Pages.
- Disable real login and label accounts as demo personas.
- Show portfolio overview, review packet, decision audit, and CSV export sample.

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

- Live Demo: planned
- Demo Video: planned
- Research Paper PDF: planned
- GitHub README: should stay short and link to detailed docs
- Demo data: synthetic/demo only
- Privacy note: no real borrower data

## Two-Minute Video Outline

1. Problem: thin-file borrowers in Pavlodar can be excluded by traditional
   credit history requirements.
2. Research finding: synthetic-data model is fragile because `late_payment_count`
   dominates.
3. Product flow: borrower application, MFI review queue, score detail, review
   packet, human decision.
4. Governance: proxy warning, timeline, audit trail, decision analytics.
5. Limitation and next step: public benchmark validation and eventual local
   pilot data.

## Non-Goals

- Do not present the demo as a real lending product.
- Do not collect real borrower personal data.
- Do not imply that synthetic results validate real-world credit decisions.
