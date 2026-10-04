# PostgreSQL Runtime v1

PostgreSQL Runtime v1 closes the gap between MicroScore's versioned PostgreSQL
schema, its 52-method repository adapter, and the FastAPI process that consumes
that repository. SQLite remains the zero-configuration default. PostgreSQL is
enabled only by explicit configuration.

## What Changed

- `create_repository()` selects SQLite or PostgreSQL from
  `MICROSCORE_STORAGE_BACKEND`.
- `PostgresRuntimeRepository` loads `psycopg`, validates the database URL,
  verifies the live schema, and bootstraps the default model registry record.
- Health and readiness responses expose only a credential-free database label.
- Shared repository exceptions keep duplicate-user, duplicate-organization,
  duplicate-model, and lifecycle behavior consistent across both backends.
- CI applies migration `0001_initial_schema`, runs an end-to-end repository
  workflow, and then drives the real FastAPI borrower/analyst lifecycle against
  disposable PostgreSQL 16.

## Configuration

```powershell
$env:MICROSCORE_STORAGE_BACKEND = "postgresql"
$env:MICROSCORE_DATABASE_URL = "postgresql://user:password@host:5432/microscore"
.venv\Scripts\python -m microscore_api.seed
.venv\Scripts\python -m uvicorn microscore_api.main:app --host 127.0.0.1 --port 8010
```

Apply the versioned migration separately before API startup:

```powershell
.venv\Scripts\python scripts\postgresql-migration-smoke.py
```

For a controlled disposable or local development database only, setting
`MICROSCORE_POSTGRES_AUTO_MIGRATE=1` makes the runtime apply known migrations
before schema verification. A deployed environment should use a separate,
audited migration job instead of automatic application startup migrations.

## Runtime Invariants

1. Backend selection is explicit; an unknown backend fails startup.
2. A PostgreSQL URL is required before the driver opens a connection.
3. Errors and health payloads never echo credentials or query parameters.
4. All required application tables must exist before the API accepts traffic.
5. The model registry always has one active default version after bootstrap.
6. PostgreSQL timestamps are normalized to the API's ISO-8601 response contract.
7. SQLite remains available as a deliberate fallback, never a silent fallback
   from failed PostgreSQL configuration.

## Disposable CI Proof

The `postgresql-migration` GitHub Actions job:

1. starts a clean `postgres:16` service;
2. validates and applies `0001_initial_schema.sql`;
3. selects the PostgreSQL runtime through the same environment variables used
   by FastAPI;
4. seeds the demo model, users, organization, applications, and scores;
5. proves session creation and revocation;
6. proves organization-scoped application reads and analyst decision writes;
7. proves invite delivery state and JSONB portfolio-simulation round trips;
8. proves segment and decision analytics;
9. reads live schema and readiness evidence through the runtime repository; and
10. runs registration, intake, scoring, review, approval, terminal guards, and
    borrower-safe history through live HTTP endpoints backed by PostgreSQL.

The executable proofs are `scripts/postgresql-runtime-smoke.py` and the
PostgreSQL mode of `scripts/live-api-workflow-smoke.py`. Fast unit tests
still use injected connection factories to isolate SQL semantics and compare
the adapter with SQLite behavior.

## What This Does Not Prove

Disposable CI proves code compatibility and repository behavior. It does not
prove any of the following:

- managed database availability or regional deployment;
- encrypted backup retention and successful restore drills;
- connection pooling and capacity under load;
- least-privilege database roles or row-level security;
- secret rotation and incident response;
- high availability, failover, or disaster recovery;
- legal authority to store real borrower information.

Consequently `production_ready` remains `false`, and the Pre-Pilot Readiness
Gate continues to block real borrower data. `compose.yaml` and
`docs/DEPLOYMENT_CANDIDATE.md` now provide a reproducible deployment candidate;
the next storage milestone is managed operational evidence, not another
repository method or another local container.
