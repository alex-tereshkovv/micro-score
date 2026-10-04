from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from microscore_api.database import REQUIRED_SCHEMA_TABLES  # noqa: E402


SCHEMA_MIGRATION_VERSION = "0001_initial_schema"
RECOVERY_TABLES = ("schema_migrations", *REQUIRED_SCHEMA_TABLES)
REQUIRED_BINARIES = ("pg_dump", "pg_restore", "createdb", "dropdb", "psql")


def recovery_contract() -> dict[str, object]:
    return {
        "mode": "postgresql-backup-restore-smoke-dry-run",
        "schema_version": SCHEMA_MIGRATION_VERSION,
        "tables_verified": len(RECOVERY_TABLES),
        "required_binaries": list(REQUIRED_BINARIES),
        "comparison": "row-count-and-full-row-fingerprint",
        "temporary_restore_database": True,
        "cleanup_required": True,
        "credentials_in_command_arguments": False,
        "production_ready": False,
    }


def _postgres_environment(database_url: str) -> tuple[dict[str, str], str, str]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("MICROSCORE_DATABASE_URL must use postgres or postgresql")
    database_name = unquote(parsed.path.lstrip("/"))
    if not parsed.hostname or not database_name:
        raise RuntimeError("MICROSCORE_DATABASE_URL must include a host and database")

    environment = os.environ.copy()
    environment.update(
        {
            "PGHOST": parsed.hostname,
            "PGPORT": str(parsed.port or 5432),
            "PGDATABASE": database_name,
        }
    )
    if parsed.username:
        environment["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        environment["PGPASSWORD"] = unquote(parsed.password)
    query = parse_qs(parsed.query)
    if query.get("sslmode"):
        environment["PGSSLMODE"] = query["sslmode"][-1]

    secret = unquote(parsed.password) if parsed.password else ""
    return environment, database_name, secret


def _sanitized(value: str, *, database_url: str, secret: str) -> str:
    result = value.replace(database_url, "[DATABASE_URL_REDACTED]")
    if secret:
        result = result.replace(secret, "[PASSWORD_REDACTED]")
    return result


def _run(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    database_url: str,
    secret: str,
) -> str:
    try:
        completed = subprocess.run(
            list(command),
            check=True,
            capture_output=True,
            text=True,
            env=dict(environment),
        )
    except subprocess.CalledProcessError as exc:
        stdout = _sanitized(exc.stdout or "", database_url=database_url, secret=secret)
        stderr = _sanitized(exc.stderr or "", database_url=database_url, secret=secret)
        raise RuntimeError(
            f"{Path(command[0]).name} failed with exit code {exc.returncode}. "
            f"stdout={stdout.strip()!r} stderr={stderr.strip()!r}"
        ) from None
    return completed.stdout.strip()


def _query(
    sql: str,
    *,
    database_name: str,
    environment: Mapping[str, str],
    database_url: str,
    secret: str,
) -> list[str]:
    output = _run(
        [
            "psql",
            "--no-psqlrc",
            "--set",
            "ON_ERROR_STOP=1",
            "--tuples-only",
            "--no-align",
            "--dbname",
            database_name,
            "--command",
            sql,
        ],
        environment=environment,
        database_url=database_url,
        secret=secret,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def _snapshot(
    *,
    database_name: str,
    environment: Mapping[str, str],
    database_url: str,
    secret: str,
) -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for table in RECOVERY_TABLES:
        rows = _query(
            f"""
            SELECT COUNT(*)::text || E'\\t' ||
                   COALESCE(
                       md5(string_agg(row_json, E'\\n' ORDER BY row_json)),
                       md5('')
                   )
            FROM (
                SELECT row_to_json(source_row)::text AS row_json
                FROM {table} AS source_row
            ) AS serialized_rows;
            """,
            database_name=database_name,
            environment=environment,
            database_url=database_url,
            secret=secret,
        )
        if len(rows) != 1 or "\t" not in rows[0]:
            raise RuntimeError(f"Unexpected fingerprint response for table {table}")
        count, fingerprint = rows[0].split("\t", 1)
        snapshot[table] = {"row_count": int(count), "fingerprint": fingerprint}
    return snapshot


def backup_restore_and_verify(database_url: str) -> dict[str, object]:
    if not database_url:
        raise RuntimeError("MICROSCORE_DATABASE_URL is required for live recovery smoke")
    missing_binaries = [name for name in REQUIRED_BINARIES if shutil.which(name) is None]
    if missing_binaries:
        raise RuntimeError(
            "Required PostgreSQL client binaries were not found: "
            + ", ".join(missing_binaries)
        )

    environment, source_database, secret = _postgres_environment(database_url)
    restore_database = f"microscore_restore_{uuid4().hex[:12]}"
    restore_created = False
    restore_dropped = False

    with tempfile.TemporaryDirectory(prefix="microscore-recovery-") as temp_directory:
        dump_path = Path(temp_directory) / "microscore.dump"
        try:
            source_snapshot = _snapshot(
                database_name=source_database,
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            _run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--file",
                    str(dump_path),
                    "--dbname",
                    source_database,
                ],
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            _run(
                ["createdb", "--maintenance-db", source_database, restore_database],
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            restore_created = True
            _run(
                [
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname",
                    restore_database,
                    str(dump_path),
                ],
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            restored_snapshot = _snapshot(
                database_name=restore_database,
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            if restored_snapshot != source_snapshot:
                mismatches = [
                    table
                    for table in RECOVERY_TABLES
                    if restored_snapshot.get(table) != source_snapshot.get(table)
                ]
                raise RuntimeError(
                    "Restored PostgreSQL data does not match the source for tables: "
                    + ", ".join(mismatches)
                )

            migration_versions = _query(
                "SELECT version FROM schema_migrations ORDER BY applied_at DESC, version DESC;",
                database_name=restore_database,
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            if SCHEMA_MIGRATION_VERSION not in migration_versions:
                raise RuntimeError(
                    f"Restored database does not contain migration {SCHEMA_MIGRATION_VERSION}"
                )
            active_model_rows = _query(
                "SELECT COUNT(*) FROM model_versions WHERE is_active IS TRUE;",
                database_name=restore_database,
                environment=environment,
                database_url=database_url,
                secret=secret,
            )
            active_model_count = int(active_model_rows[0]) if active_model_rows else 0
            if active_model_count != 1:
                raise RuntimeError(
                    "Restored database must contain exactly one active model version; "
                    f"found {active_model_count}"
                )

            dump_bytes = dump_path.read_bytes()
            result = {
                "mode": "postgresql-backup-restore-smoke",
                "schema_version": SCHEMA_MIGRATION_VERSION,
                "tables_verified": len(RECOVERY_TABLES),
                "rows_verified": sum(
                    int(value["row_count"]) for value in source_snapshot.values()
                ),
                "fingerprints_match": True,
                "active_model_count": active_model_count,
                "dump_bytes": len(dump_bytes),
                "dump_sha256": hashlib.sha256(dump_bytes).hexdigest(),
                "temporary_restore_database": True,
                "credentials_in_output": False,
                "production_ready": False,
            }
        finally:
            if restore_created:
                _run(
                    [
                        "dropdb",
                        "--if-exists",
                        "--maintenance-db",
                        source_database,
                        restore_database,
                    ],
                    environment=environment,
                    database_url=database_url,
                    secret=secret,
                )
                restore_dropped = True

    result["restore_database_dropped"] = restore_dropped
    if not restore_dropped:
        raise RuntimeError("Temporary restore database cleanup was not confirmed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a credential-safe PostgreSQL dump and disposable restore."
    )
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    if arguments.dry_run:
        print(json.dumps(recovery_contract(), indent=2, sort_keys=True))
        return 0

    database_url = os.environ.get("MICROSCORE_DATABASE_URL", "")
    try:
        result = backup_restore_and_verify(database_url)
    except Exception as exc:
        safe_message = _sanitized(
            str(exc),
            database_url=database_url,
            secret=urlparse(database_url).password or "",
        )
        print(
            f"::error title=PostgreSQL recovery smoke failed::{safe_message}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
