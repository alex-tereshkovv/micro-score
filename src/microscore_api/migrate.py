"""Run known PostgreSQL migrations as an explicit deployment step."""

from __future__ import annotations

import json
import os

from .postgres_runtime import PostgresRuntimeRepository


def main() -> int:
    backend = os.environ.get("MICROSCORE_STORAGE_BACKEND", "").strip().lower()
    if backend != "postgresql":
        raise RuntimeError(
            "The migration command requires MICROSCORE_STORAGE_BACKEND=postgresql."
        )
    database_url = os.environ.get("MICROSCORE_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("MICROSCORE_DATABASE_URL is required for migrations.")

    repository = PostgresRuntimeRepository(database_url, initialize=False)
    applied = repository.apply_migrations()
    repository.initialize()
    readiness = repository.postgresql_migration_readiness()
    print(
        json.dumps(
            {
                "mode": "postgresql-migrate",
                "backend": repository.storage_backend,
                "database": repository.database_label,
                "applied_migrations": applied,
                "present_tables": readiness["present_table_count"],
                "required_tables": readiness["required_table_count"],
                "production_ready": readiness["production_ready"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
