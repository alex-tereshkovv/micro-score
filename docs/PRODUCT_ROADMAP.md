# MicroScore Product Roadmap

Target: by November 9, 2026, MicroScore should be a working web application
where a real borrower can create an account, submit financial-behavior data, and
an MFI user can review risk scores, explanations, and portfolio analytics.

This roadmap assumes the current date is June 9, 2026.

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
- application submission status

MFI side:

- secure analyst login
- application list
- borrower-level risk summary
- model probability and risk band
- top contributing factors
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
- top factors and explanations
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

Deliverable: working portfolio-ready MVP with auth, borrower submission, MFI
dashboard, risk scoring, and analytics.

## Product Risks

- Real borrower data requires privacy, consent, and security controls.
- Synthetic model performance must not be overstated.
- Regional assumptions must be clearly labeled until replaced by measured data.
- The first version should support loan officers, not replace them.
- Any real MFI pilot needs anonymization and a written data-use agreement.

## Near-Term Next Step

The first backend scaffold now exists in `src/microscore_api/`. The next
engineering milestone is to replace in-memory state with a real persistence
layer:

- PostgreSQL or SQLite development database
- persistent users, applications, scores, and audit events
- migration workflow
- stronger password and session handling
- seeded demo accounts for borrower and MFI analyst roles
