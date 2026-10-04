# PostgreSQL Recovery Gate v1

MicroScore now proves one narrow but important operational claim: the database
created by the disposable PostgreSQL workflow can be dumped, restored into a
clean database, and compared without losing schema or content.

This is recovery engineering evidence, not a production backup guarantee.

## Automated drill

The `postgresql-migration` CI job runs the following sequence after the live
FastAPI/PostgreSQL workflow has created realistic synthetic state:

1. `pg_dump` creates a custom-format archive without ownership or privilege
   statements.
2. `createdb` creates a uniquely named, disposable restore target.
3. `pg_restore` loads the archive with `--exit-on-error`.
4. The source and restored databases are fingerprinted independently.
5. All 12 tables must have identical row counts and MD5 fingerprints of their
   complete JSON-serialized rows.
6. The restored database must contain migration `0001_initial_schema` and
   exactly one active model version.
7. `dropdb` removes the restore target from a `finally` block, including when a
   validation fails.

Run the contract-only check locally:

```powershell
.venv\Scripts\python.exe scripts\postgresql-backup-restore-smoke.py --dry-run
```

Run the live drill only against an explicitly disposable database:

```powershell
$env:MICROSCORE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DATABASE"
.venv\Scripts\python.exe scripts\postgresql-backup-restore-smoke.py
```

The script passes credentials to PostgreSQL tools through `PG*` environment
variables, not command arguments. Errors redact the full database URL and the
decoded password. The JSON result contains counts and archive metadata, never
the source or restore database name.

## What the drill detects

- a dump or restore command that fails;
- a missing table, row, or changed row value after restore;
- a missing schema migration record;
- a broken active-model invariant;
- a restore target that cannot be cleaned up.

## What remains unverified

The disposable CI drill does **not** establish:

- a recovery point objective (RPO) or recovery time objective (RTO);
- scheduled, encrypted, off-site, or immutable backups;
- retention and deletion policy enforcement;
- restore into a managed cloud PostgreSQL service;
- point-in-time recovery or write-ahead-log archiving;
- key rotation, least-privilege backup roles, or operator access review;
- recovery under production data volume, partial corruption, or regional loss.

These remain mandatory pilot gates. `production_ready` therefore stays false.

## Managed recovery runbook

Before any real borrower data is admitted, the operator must:

1. document the approved managed PostgreSQL service and backup owner;
2. select and approve target RPO/RTO values;
3. enable encrypted automated backups and point-in-time recovery;
4. define retention, deletion, geographic replication, and access policies;
5. restore the latest backup into an isolated managed environment;
6. run migration, table-fingerprint, active-model, tenant-scope, and application
   lifecycle checks against that environment;
7. record start/end times, backup age, artifact identity, results, deviations,
   and responsible reviewer;
8. destroy the isolated environment and verify deletion;
9. repeat on a schedule and after material schema or infrastructure changes.

An operator may only claim the measured RPO/RTO from a recorded managed drill;
the CI result must not be substituted for that evidence.
