# Deployment Candidate v1

Deployment Candidate v1 packages the current synthetic MicroScore product as a
reproducible four-stage local environment:

```text
browser -> static web -> FastAPI -> PostgreSQL 16
                                  ^
                         migration + seed jobs
```

It exists to prove that the application can be assembled from clean containers
and that the HTTP API actually uses PostgreSQL. It is still a demonstration
environment, not authorization to process real borrower data.

## Start The Stack

Docker Desktop or another current Docker Compose implementation is required.
From the repository root:

```powershell
Copy-Item .env.compose.example .env
docker compose up --build --detach
docker compose ps
```

Open `http://127.0.0.1:5173`. The API health endpoint is available at
`http://127.0.0.1:8010/health`.

The example password is deliberately labeled local-only. Change it before any
shared demonstration environment. Never commit the generated `.env` file.

## Lifecycle

The Compose dependency graph is intentional:

1. `postgres` starts with an internal-only database port and must become healthy.
2. `migrate` runs `python -m microscore_api.migrate` and exits successfully.
3. `seed` creates the synthetic organization, accounts, portfolio, and scores.
4. `api` starts only after seeding and reports PostgreSQL through `/health`.
5. `web` starts only after the API healthcheck passes.

The API and web containers run read-only, use non-root application processes,
and receive writable temporary filesystems only for runtime scratch data.

Useful commands:

```powershell
docker compose logs --follow api
docker compose logs --follow migrate seed
docker compose down
docker compose down --volumes  # also deletes the synthetic local database
```

## Automated Proof

GitHub Actions provides two distinct proofs:

- `Disposable PostgreSQL migration smoke` runs the full borrower-to-decision
  live HTTP workflow through FastAPI against PostgreSQL 16.
- `Container deployment candidate smoke` validates the Compose model, builds
  both images, runs migration and seed jobs, waits for API/web health, and
  verifies that `/health` reports PostgreSQL without exposing credentials.

The same `scripts/live-api-workflow-smoke.py` runs against temporary SQLite in
the local release gate and against PostgreSQL in CI. This prevents backend
parity from becoming a separate, weaker test path.

## What This Does Not Prove

This stack does not prove managed hosting, TLS termination, external identity,
secret management, encrypted backups, restore drills, high availability,
capacity, regulatory compliance, or permission to store personal data. The
public GitHub Pages demo remains browser-local and synthetic. The admin
Pre-Pilot Readiness Gate must continue to report `production_data_allowed=false`.
