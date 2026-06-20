# MicroScore Product Roadmap

Target: by November 9, 2026, MicroScore should be a working web application
where a real borrower can create an account, submit financial-behavior data, and
an MFI user can review risk scores, explanations, and portfolio analytics.

This roadmap was refreshed on June 20, 2026.

## Product Vision

MicroScore should become a lightweight decision-support system for regional
microfinance organizations in Kazakhstan.

It should support two user types:

- Borrower: creates an account, submits consent-based financial and behavioral
  information, and can view a simple application status.
- MFI analyst or loan officer: reviews applications, risk scores, explanations,
  segment analytics, and threshold trade-offs.

The system should not automatically approve or reject loans in the first
production version. It should support human decision-making.

## MVP Scope

Borrower side:

- account registration and login
- consent screen
- borrower profile
- loan application form
- financial-behavior questionnaire
- application submission status and timeline

MFI side:

- secure analyst login
- application list
- application timeline/status history
- borrower-level risk summary
- model probability and risk band
- top contributing factors
- decision-support recommendation
- regional context
- fairness/segment analytics
- threshold decision analysis

Admin/research side:

- model version tracking
- audit tables
- exportable CSV reports
- reproducible experiment commands

## Suggested Technical Architecture

Frontend:

- React or Next.js
- dashboard views for MFI analysts
- separate borrower flow

Backend:

- Python FastAPI
- REST API for applications, scoring, analytics, and user management
- background job for scoring if needed later

Database:

- PostgreSQL
- separate tables for users, borrower profiles, applications, score results,
  model versions, and audit logs

Authentication:

- email/password for MVP
- role-based access control: `borrower`, `mfi_analyst`, `admin`
- MFA can be added later for MFI/admin accounts

ML service:

- package current `microscore` pipeline as an internal scoring module
- store model version and feature schema
- return probability, risk band, explanations, and warnings

Deployment:

- local Docker Compose for development
- cloud deployment later, after privacy and security review

## Data Model Draft

Core entities:

- `users`
- `borrower_profiles`
- `loan_applications`
- `behavioral_signals`
- `score_results`
- `model_versions`
- `mfi_organizations`
- `audit_events`

Minimum score result fields:

- application id
- model version
- predicted high-risk probability
- risk band
- top positive factors
- top protective factors
- scenario comparison
- decision-support recommendation
- threshold recommendation
- created timestamp

## API Draft

Borrower endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `GET /me`
- `POST /applications`
- `GET /applications/{id}`

MFI endpoints:

- `GET /mfi/applications`
- `GET /mfi/applications/{id}`
- `POST /mfi/applications/{id}/score`
- `GET /mfi/analytics/segments`
- `GET /mfi/analytics/thresholds`

Research/admin endpoints:

- `GET /admin/model-versions`
- `POST /admin/model-versions`
- `GET /admin/audit-events`

## Five-Month Plan

### Month 1: June 9 - July 9, 2026

Goal: stabilize research foundation and product specification.

- finish methodology documentation
- define product roles and user flows
- create app architecture
- add model card template
- add calibration metrics
- add no-repayment-history scenario
- design database schema
- publish data statement and impact plan
- prepare research paper draft

Deliverable: research repo plus product specification.

### Month 2: July 10 - August 9, 2026

Goal: build backend foundation.

- create FastAPI backend
- add PostgreSQL schema
- implement authentication
- implement borrower profile and loan application APIs
- connect current scoring module to backend
- add audit logging

Deliverable: local backend API with auth and scoring.

### Month 3: August 10 - September 9, 2026

Goal: build borrower-facing application.

- create frontend app
- registration and login flow
- consent and privacy notice
- borrower profile form
- loan application form
- application status page
- connect frontend to backend

Deliverable: real user can register and submit an application.

### Month 4: September 10 - October 9, 2026

Goal: build MFI analytics dashboard.

- analyst login
- application queue
- borrower risk detail page
- application timeline/status history
- top factors and explanations
- analyst decision capture
- review packet with governance flags and human-review checklist
- analyst decision analytics by risk, district, proxy sensitivity, and recommendation
- threshold analytics
- regional/segment dashboards
- CSV export for pilot demos

Deliverable: MFI analyst can review applications and analytics.

### Month 5: October 10 - November 9, 2026

Goal: polish, security, and demo readiness.

- improve UI/UX
- add password reset or admin-managed accounts
- add role-based permissions
- add model/version warnings
- add deployment instructions
- write final project report
- prepare demo dataset and demo script
- deploy public demo or simplified reviewer demo
- record two-minute walkthrough video

Deliverable: working portfolio-ready MVP with auth, borrower submission, MFI
dashboard, risk scoring, and analytics.

## Product Risks

- Real borrower data requires privacy, consent, and security controls.
- Synthetic model performance must not be overstated.
- Regional assumptions must be clearly labeled until replaced by measured data.
- The first version should support loan officers, not replace them.
- Any real MFI pilot needs anonymization and a written data-use agreement.

## Near-Term Next Step

The first backend scaffold now exists in `src/microscore_api/`, and it now uses
SQLite persistence for users, sessions, applications, score results, model
versions, and audit events. The API also has demo seed data, typed response schemas, an API contract
document, integration tests for the complete borrower/MFI/admin flow, dual
standard/thin-file scoring, decision-support recommendations, and a static web
prototype in `apps/web/`. The MFI workspace now includes application timeline
views, review packets, portfolio CSV export, decision audit analytics, and a
Policy Lab that compares approve/review/decline threshold policies on scored
applications. Model governance now includes candidate registration, atomic
activation, immutable score provenance, and stale-score warnings in analyst
review packets. The Policy Lab also includes a reproducible, tenant-scoped
Monte Carlo layer for portfolio outcome ranges under baseline, adverse, and
severe assumptions; it is explicitly separated from borrower scoring. The
project also now generates reproducible research artifacts under
`reports/research-artifacts/`: model metrics, ablation results, calibration
bins, calibration/ablation plots, and example local explanations.
Borrower lifecycle v2 now adds automatic owned-application history, a visual status
progression, borrower-safe API projections, and strict terminal-state guards
across the local API and static demo.
The next engineering milestone is to turn the
frontend and scoring review flow into a more production-like application:

- stronger client-side form validation
- richer MFI risk detail page
- district and settlement-type charts
- dedicated frontend integration tests
- screenshot-ready dashboard states for portfolio review
- public demo plan: Vercel/Netlify frontend plus hosted API or Streamlit review app
- two-minute demo video script
- stakeholder interviews and validation tracker updates
- real KZT feature calibration before pilot use
- eventual React or Next.js migration when the product flow stabilizes
- migration path from SQLite development storage to PostgreSQL
- stronger password and session handling before any real user data
