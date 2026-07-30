from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from microscore_api.database import (  # noqa: E402
    JSON_TEXT_COLUMNS,
    POSTGRESQL_TENANT_SCOPE_INDEXES,
    REQUIRED_SCHEMA_TABLES,
)
from microscore_api.postgres_repository import (  # noqa: E402
    POSTGRESQL_AUDIT_METHODS,
    POSTGRESQL_MODEL_REGISTRY_METHODS,
    POSTGRESQL_MODEL_REGISTRY_READ_METHODS,
    POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS,
)


DEFAULT_MIGRATION_PATH = (
    PROJECT_ROOT / "migrations" / "postgresql" / "0001_initial_schema.sql"
)
SCHEMA_MIGRATION_VERSION = "0001_initial_schema"
EXPECTED_TABLES = (*REQUIRED_SCHEMA_TABLES, "schema_migrations")


def _load_migration(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Migration file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def validate_migration_text(path: Path) -> dict[str, object]:
    sql = _load_migration(path)
    missing_tables = [
        table
        for table in EXPECTED_TABLES
        if f"CREATE TABLE IF NOT EXISTS {table}" not in sql
    ]
    missing_jsonb_columns = [
        item
        for item in JSON_TEXT_COLUMNS
        if f"{item.split('.', 1)[1]} JSONB" not in sql
    ]
    missing_tenant_indexes = [
        index_name
        for index_name in POSTGRESQL_TENANT_SCOPE_INDEXES
        if f"CREATE INDEX IF NOT EXISTS {index_name}" not in sql
    ]
    if SCHEMA_MIGRATION_VERSION not in sql:
        raise RuntimeError(f"{SCHEMA_MIGRATION_VERSION} is not recorded in migration SQL")
    if missing_tables or missing_jsonb_columns or missing_tenant_indexes:
        raise RuntimeError(
            "PostgreSQL migration draft is incomplete: "
            + json.dumps(
                {
                    "missing_tables": missing_tables,
                    "missing_jsonb_columns": missing_jsonb_columns,
                    "missing_tenant_indexes": missing_tenant_indexes,
                },
                sort_keys=True,
            )
        )
    return {
        "migration": path.relative_to(PROJECT_ROOT).as_posix(),
        "version": SCHEMA_MIGRATION_VERSION,
        "expected_tables": len(EXPECTED_TABLES),
        "expected_jsonb_columns": len(JSON_TEXT_COLUMNS),
        "expected_tenant_indexes": len(POSTGRESQL_TENANT_SCOPE_INDEXES),
        "expected_model_registry_read_methods": len(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "expected_model_registry_write_methods": len(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS),
        "expected_model_registry_methods": len(POSTGRESQL_MODEL_REGISTRY_METHODS),
        "expected_audit_methods": len(POSTGRESQL_AUDIT_METHODS),
    }


def run_psql(
    *,
    psql_bin: str,
    database_url: str,
    arguments: Sequence[str],
) -> str:
    command = [
        psql_bin,
        "--no-psqlrc",
        "--set",
        "ON_ERROR_STOP=1",
        "--dbname",
        database_url,
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            "psql failed with exit code "
            f"{exc.returncode}. stdout={stdout!r} stderr={stderr!r}"
        ) from None
    return completed.stdout.strip()


def query_rows(*, psql_bin: str, database_url: str, sql: str) -> list[str]:
    output = run_psql(
        psql_bin=psql_bin,
        database_url=database_url,
        arguments=[
            "--tuples-only",
            "--no-align",
            "--field-separator",
            "\t",
            "--command",
            sql,
        ],
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def assert_catalog_subset(
    *,
    expected: Sequence[str],
    actual: Sequence[str],
    label: str,
) -> None:
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise RuntimeError(f"Missing PostgreSQL {label}: {', '.join(missing)}")


def apply_migration_and_verify(
    *,
    migration_path: Path,
    database_url: str,
    psql_bin: str,
) -> dict[str, object]:
    if not database_url:
        raise RuntimeError("MICROSCORE_DATABASE_URL is required for live PostgreSQL smoke")
    if shutil.which(psql_bin) is None:
        raise RuntimeError(f"psql binary was not found: {psql_bin}")

    run_psql(
        psql_bin=psql_bin,
        database_url=database_url,
        arguments=["--file", str(migration_path)],
    )
    run_psql(
        psql_bin=psql_bin,
        database_url=database_url,
        arguments=[
            "--command",
            """
            INSERT INTO mfi_organizations (id, name, region, created_at)
            VALUES ('ci-smoke-mfi', 'CI Smoke MFI', 'Pavlodar', NOW())
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

            INSERT INTO users (email, password_hash, role, organization_id, created_at)
            VALUES
                ('ci-smoke-borrower@example.com', 'hash', 'borrower', NULL, NOW()),
                ('ci-smoke-analyst@example.com', 'hash', 'mfi_analyst', 'ci-smoke-mfi', NOW())
            ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role;

            INSERT INTO loan_applications (
                id,
                borrower_email,
                status,
                requested_amount,
                purpose,
                district,
                settlement_type,
                organization_id,
                behavioral_signals_json,
                score_result_json,
                created_at,
                scored_at
            )
            VALUES (
                'ci-smoke-application',
                'ci-smoke-borrower@example.com',
                'scored',
                125000.00,
                'postgresql migration smoke',
                'Pavlodar city',
                'urban',
                'ci-smoke-mfi',
                '{"mobile_logins": 4, "late_payment_count": 0}'::jsonb,
                '{"risk_band": "low", "score": 0.82}'::jsonb,
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO UPDATE
            SET score_result_json = EXCLUDED.score_result_json;

            UPDATE model_versions
            SET lifecycle_status = 'inactive', is_active = FALSE
            WHERE version IN ('ci-smoke-model', 'ci-smoke-model-candidate');

            INSERT INTO model_versions (
                version,
                model_name,
                model_type,
                lifecycle_status,
                is_active,
                feature_schema_version,
                training_data_label,
                random_state,
                metrics_json,
                limitations_json,
                created_by,
                created_at,
                activated_at
            )
            VALUES (
                'ci-smoke-model',
                'CI Smoke Model',
                'logistic_regression',
                'inactive',
                FALSE,
                'behavioral-v1',
                'ci-smoke',
                42,
                '{"roc_auc": 0.81}'::jsonb,
                '["disposable CI smoke only"]'::jsonb,
                'ci',
                NOW(),
                NOW()
            )
            ON CONFLICT (version) DO UPDATE
            SET
                lifecycle_status = EXCLUDED.lifecycle_status,
                is_active = EXCLUDED.is_active,
                metrics_json = EXCLUDED.metrics_json,
                activated_at = EXCLUDED.activated_at;

            INSERT INTO model_versions (
                version,
                model_name,
                model_type,
                lifecycle_status,
                is_active,
                feature_schema_version,
                training_data_label,
                random_state,
                metrics_json,
                limitations_json,
                created_by,
                created_at,
                activated_at
            )
            VALUES (
                'ci-smoke-model-candidate',
                'CI Smoke Candidate Model',
                'logistic_regression',
                'candidate',
                FALSE,
                'behavioral-v2',
                'ci-smoke-candidate',
                43,
                '{"roc_auc": 0.84}'::jsonb,
                '["disposable CI write smoke only"]'::jsonb,
                'ci',
                NOW(),
                NULL
            )
            ON CONFLICT (version) DO UPDATE
            SET
                lifecycle_status = EXCLUDED.lifecycle_status,
                is_active = EXCLUDED.is_active,
                metrics_json = EXCLUDED.metrics_json,
                activated_at = EXCLUDED.activated_at;

            UPDATE model_versions
            SET lifecycle_status = 'inactive', is_active = FALSE
            WHERE is_active IS TRUE AND version <> 'ci-smoke-model-candidate';

            UPDATE model_versions
            SET lifecycle_status = 'active', is_active = TRUE, activated_at = NOW()
            WHERE version = 'ci-smoke-model-candidate';

            INSERT INTO audit_events (
                actor_email,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES (
                'ci-smoke-analyst@example.com',
                'postgresql_audit_adapter_smoke',
                'postgres_repository',
                'audit',
                '{"method_group": "audit", "complete": true}'::jsonb,
                NOW()
            );
            """,
        ],
    )

    tables = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """,
    )
    jsonb_columns = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT table_name || '.' || column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND data_type = 'jsonb'
            ORDER BY 1;
        """,
    )
    indexes = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY indexname;
        """,
    )
    schema_version = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT version
            FROM schema_migrations
            WHERE version = '0001_initial_schema';
        """,
    )
    jsonb_value = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT score_result_json->>'risk_band'
            FROM loan_applications
            WHERE id = 'ci-smoke-application';
        """,
    )
    active_model_version = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT version
            FROM model_versions
            WHERE is_active IS TRUE
            ORDER BY activated_at DESC NULLS LAST, created_at DESC, version DESC
            LIMIT 1;
        """,
    )
    active_model_metric = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT metrics_json->>'roc_auc'
            FROM model_versions
            WHERE version = 'ci-smoke-model-candidate';
        """,
    )
    active_model_status = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT lifecycle_status || ':' || is_active::text
            FROM model_versions
            WHERE version = 'ci-smoke-model-candidate';
        """,
    )
    latest_audit_action = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT action
            FROM audit_events
            ORDER BY id DESC
            LIMIT 1;
        """,
    )
    latest_audit_detail = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT details_json->>'method_group'
            FROM audit_events
            WHERE action = 'postgresql_audit_adapter_smoke'
            ORDER BY id DESC
            LIMIT 1;
        """,
    )

    assert_catalog_subset(expected=EXPECTED_TABLES, actual=tables, label="tables")
    assert_catalog_subset(
        expected=JSON_TEXT_COLUMNS,
        actual=jsonb_columns,
        label="jsonb columns",
    )
    assert_catalog_subset(
        expected=POSTGRESQL_TENANT_SCOPE_INDEXES,
        actual=indexes,
        label="tenant-scope indexes",
    )
    assert_catalog_subset(
        expected=[SCHEMA_MIGRATION_VERSION],
        actual=schema_version,
        label="schema migration version",
    )
    assert_catalog_subset(expected=["low"], actual=jsonb_value, label="JSONB smoke row")
    assert_catalog_subset(
        expected=["ci-smoke-model-candidate"],
        actual=active_model_version,
        label="active model registry row",
    )
    assert_catalog_subset(
        expected=["0.84"],
        actual=active_model_metric,
        label="model registry JSONB metric",
    )
    assert_catalog_subset(
        expected=["active:true"],
        actual=active_model_status,
        label="model registry activation status",
    )
    assert_catalog_subset(
        expected=["postgresql_audit_adapter_smoke"],
        actual=latest_audit_action,
        label="latest audit action",
    )
    assert_catalog_subset(
        expected=["audit"],
        actual=latest_audit_detail,
        label="audit JSONB details",
    )

    return {
        "migration": migration_path.relative_to(PROJECT_ROOT).as_posix(),
        "version": SCHEMA_MIGRATION_VERSION,
        "tables": len(tables),
        "required_tables": len(EXPECTED_TABLES),
        "jsonb_columns": len(jsonb_columns),
        "required_jsonb_columns": len(JSON_TEXT_COLUMNS),
        "tenant_indexes": len(
            set(indexes).intersection(POSTGRESQL_TENANT_SCOPE_INDEXES)
        ),
        "required_tenant_indexes": len(POSTGRESQL_TENANT_SCOPE_INDEXES),
        "jsonb_smoke_row": jsonb_value[0],
        "model_registry_active_version": active_model_version[0],
        "model_registry_metric_roc_auc": active_model_metric[0],
        "model_registry_read_methods": len(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "model_registry_write_methods": len(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS),
        "model_registry_methods": len(POSTGRESQL_MODEL_REGISTRY_METHODS),
        "audit_methods": len(POSTGRESQL_AUDIT_METHODS),
        "audit_latest_action": latest_audit_action[0],
        "audit_detail_method_group": latest_audit_detail[0],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply and verify the MicroScore PostgreSQL migration draft.",
    )
    parser.add_argument(
        "--migration",
        type=Path,
        default=DEFAULT_MIGRATION_PATH,
        help="Path to the PostgreSQL migration SQL file.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("MICROSCORE_DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to MICROSCORE_DATABASE_URL.",
    )
    parser.add_argument(
        "--psql-bin",
        default=os.environ.get("PSQL_BIN", "psql"),
        help="psql executable name or path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate migration text only; do not connect to PostgreSQL.",
    )
    return parser.parse_args()


def main() -> None:
    try:
        args = parse_args()
        migration_path = args.migration.resolve()
        text_summary = validate_migration_text(migration_path)
        if args.dry_run:
            result = {"mode": "postgresql-migration-smoke-dry-run", **text_summary}
        else:
            result = {
                "mode": "postgresql-migration-smoke",
                **apply_migration_and_verify(
                    migration_path=migration_path,
                    database_url=args.database_url,
                    psql_bin=args.psql_bin,
                ),
            }
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        message = str(exc).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=PostgreSQL migration smoke failed::{message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
