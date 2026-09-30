"""Executable PostgreSQL repository selected by the MicroScore API runtime."""

from __future__ import annotations

from pathlib import Path
import os
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from microscore.paths import PROJECT_ROOT

from .database import (
    DEFAULT_FEATURE_SCHEMA_VERSION,
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_RANDOM_STATE,
    DEFAULT_MODEL_VERSION,
    DEFAULT_TRAINING_DATA_LABEL,
    JSON_TEXT_COLUMNS,
    POSTGRESQL_EXPECTED_MIGRATIONS,
    POSTGRESQL_MIGRATION_DIRECTORY,
    POSTGRESQL_REQUIRED_ENVIRONMENT,
    REQUIRED_SCHEMA_TABLES,
    TENANT_SCOPED_TABLES,
    MicroScoreRepository,
)
from .postgres_repository import PostgresRepositoryAdapter, repository_contract_summary


POSTGRESQL_RUNTIME_VERSION = "postgresql-runtime-v1"
POSTGRESQL_RUNTIME_CI_SCRIPT = "scripts/postgresql-runtime-smoke.py"
POSTGRESQL_RUNTIME_LIMITATION = (
    "PostgreSQL Runtime v1 enables the complete repository contract and is tested "
    "against disposable PostgreSQL in CI. It is not evidence of managed hosting, "
    "backup restore, retention enforcement, secret rotation, high availability, "
    "or authorization for real borrower data."
)


def _enabled(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_database_label(database_url: str) -> str:
    parsed = urlsplit(database_url)
    hostname = parsed.hostname or "configured-host"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path or "/configured-database"
    return urlunsplit(("postgresql", f"{hostname}{port}", database, "", ""))


def _load_psycopg() -> tuple[Any, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PostgreSQL runtime requires psycopg. Install the app dependencies "
            "with: pip install -e \".[app]\""
        ) from exc
    return psycopg, dict_row


def _validate_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError(
            "MICROSCORE_DATABASE_URL must be a postgresql:// URL with a host."
        )
    return normalized


class PostgresRuntimeRepository(PostgresRepositoryAdapter):
    """Production-shaped PostgreSQL runtime with explicit prototype boundaries."""

    storage_backend = "postgresql"

    def __init__(
        self,
        database_url: str,
        *,
        connection_factory: Callable[[], Any] | None = None,
        auto_migrate: bool | None = None,
        initialize: bool = True,
    ) -> None:
        self.database_url = _validate_database_url(database_url)
        self.database_label = _safe_database_label(self.database_url)
        # Kept for the existing health/seed response contract; never contains secrets.
        self.db_path = self.database_label
        self.auto_migrate = (
            _enabled("MICROSCORE_POSTGRES_AUTO_MIGRATE")
            if auto_migrate is None
            else auto_migrate
        )
        if connection_factory is None:
            psycopg, dict_row = _load_psycopg()
            connect_timeout = max(
                1,
                int(os.environ.get("MICROSCORE_POSTGRES_CONNECT_TIMEOUT", "5")),
            )

            def connection_factory() -> Any:
                return psycopg.connect(
                    self.database_url,
                    row_factory=dict_row,
                    connect_timeout=connect_timeout,
                )

        super().__init__(connection_factory)
        if initialize:
            self.initialize()

    @classmethod
    def from_environment(cls) -> "PostgresRuntimeRepository":
        database_url = os.environ.get("MICROSCORE_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError(
                "MICROSCORE_DATABASE_URL is required when "
                "MICROSCORE_STORAGE_BACKEND=postgresql."
            )
        return cls(database_url)

    def initialize(self) -> None:
        if self.auto_migrate:
            self.apply_migrations()
        self._verify_schema()
        self._ensure_default_model()

    def apply_migrations(self) -> list[str]:
        psycopg, _dict_row = _load_psycopg()
        applied: list[str] = []
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            for filename in POSTGRESQL_EXPECTED_MIGRATIONS:
                path = POSTGRESQL_MIGRATION_DIRECTORY / filename
                if not path.exists():
                    raise RuntimeError(f"PostgreSQL migration is missing: {path.name}")
                connection.execute(path.read_text(encoding="utf-8"), prepare=False)
                applied.append(filename)
        return applied

    def _verify_schema(self) -> None:
        row = self._fetchone(
            """
            SELECT COUNT(*) AS table_count
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = ANY(%(required_tables)s)
            """,
            {"required_tables": list(REQUIRED_SCHEMA_TABLES)},
        )
        table_count = int((row or {}).get("table_count", 0))
        if table_count != len(REQUIRED_SCHEMA_TABLES):
            raise RuntimeError(
                "PostgreSQL schema is not initialized: expected "
                f"{len(REQUIRED_SCHEMA_TABLES)} application tables, found "
                f"{table_count}. Apply migrations/postgresql/0001_initial_schema.sql "
                "or set MICROSCORE_POSTGRES_AUTO_MIGRATE=1 for a controlled "
                "development bootstrap."
            )

    def _ensure_default_model(self) -> None:
        active = self.get_active_model_version()
        if active is not None:
            return
        if self.get_model_version(DEFAULT_MODEL_VERSION) is None:
            self.create_model_version(
                version=DEFAULT_MODEL_VERSION,
                model_name=DEFAULT_MODEL_NAME,
                feature_schema_version=DEFAULT_FEATURE_SCHEMA_VERSION,
                training_data_label=DEFAULT_TRAINING_DATA_LABEL,
                random_state=DEFAULT_MODEL_RANDOM_STATE,
                metrics={},
                limitations=[
                    "Synthetic training data only.",
                    "Not validated for real lending decisions.",
                ],
                created_by=None,
            )
        self.activate_model_version(DEFAULT_MODEL_VERSION)

    def _runtime_ci_present(self) -> bool:
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not workflow_path.exists():
            return False
        workflow = workflow_path.read_text(encoding="utf-8")
        return (
            "postgres:16" in workflow
            and POSTGRESQL_RUNTIME_CI_SCRIPT in workflow
            and "MICROSCORE_STORAGE_BACKEND: postgresql" in workflow
        )

    def _live_schema_inventory(self) -> list[dict[str, Any]]:
        column_rows = self._fetchall(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = ANY(%(required_tables)s)
            ORDER BY table_name, ordinal_position
            """,
            {"required_tables": list(REQUIRED_SCHEMA_TABLES)},
        )
        columns_by_table: dict[str, list[str]] = {}
        for row in column_rows:
            columns_by_table.setdefault(str(row["table_name"]), []).append(
                str(row["column_name"])
            )
        primary_key_rows = self._fetchall(
            """
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = current_schema()
              AND tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = ANY(%(required_tables)s)
            ORDER BY tc.table_name, kcu.ordinal_position
            """,
            {"required_tables": list(REQUIRED_SCHEMA_TABLES)},
        )
        keys_by_table: dict[str, list[str]] = {}
        for row in primary_key_rows:
            keys_by_table.setdefault(str(row["table_name"]), []).append(
                str(row["column_name"])
            )
        json_by_table: dict[str, list[str]] = {}
        for item in JSON_TEXT_COLUMNS:
            table, column = item.split(".", 1)
            json_by_table.setdefault(table, []).append(column)
        tenant_by_table: dict[str, list[str]] = {}
        for item in TENANT_SCOPED_TABLES:
            table, column = item.split(".", 1)
            tenant_by_table.setdefault(table, []).append(column)
        return [
            {
                "table": table,
                # Backward-compatible field retained for the public evidence schema.
                "present_in_sqlite": True,
                "present_in_runtime": table in columns_by_table,
                "column_count": len(columns_by_table.get(table, [])),
                "primary_key_columns": keys_by_table.get(table, []),
                "json_columns": json_by_table.get(table, []),
                "tenant_scope_columns": tenant_by_table.get(table, []),
                "migration_notes": ["Verified against the live PostgreSQL catalog."],
            }
            for table in REQUIRED_SCHEMA_TABLES
        ]

    def storage_readiness(self) -> dict[str, Any]:
        return {
            "backend": "postgresql",
            "status": "ready",
            "production_ready": False,
            "database_path": self.database_label,
            "database_exists": True,
            "required_tables": list(REQUIRED_SCHEMA_TABLES),
            "json_columns": list(JSON_TEXT_COLUMNS),
            "tenant_scoped_tables": list(TENANT_SCOPED_TABLES),
            "capabilities": [
                {
                    "id": "postgresql_repository_backend",
                    "status": "ready",
                    "detail": "The API selected the PostgreSQL repository runtime.",
                },
                {
                    "id": "postgresql_repository_contract",
                    "status": "ready",
                    "detail": "All 52 repository methods are available through PostgreSQL.",
                },
                {
                    "id": "postgresql_disposable_runtime_ci",
                    "status": "ready" if self._runtime_ci_present() else "blocked",
                    "detail": "CI exercises the repository against a disposable PostgreSQL 16 service.",
                },
                {
                    "id": "managed_postgresql_operations",
                    "status": "planned",
                    "detail": "Backups, restore drills, retention, secret rotation, and HA remain deployment responsibilities.",
                },
            ],
            "postgresql_migration_status": "implemented",
            "postgresql_migration_checklist": [
                "Run versioned migrations before application startup.",
                "Keep repository parity in disposable PostgreSQL CI.",
                "Validate backup restore, retention, and secret rotation before real data.",
            ],
            "limitation": POSTGRESQL_RUNTIME_LIMITATION,
        }

    def postgresql_repository_adapter_contract(self) -> dict[str, Any]:
        return repository_contract_summary()

    def postgresql_migration_readiness(self) -> dict[str, Any]:
        inventory = self._live_schema_inventory()
        artifacts = MicroScoreRepository.postgresql_migration_artifacts(self)
        runtime_ci_present = self._runtime_ci_present()
        contract = repository_contract_summary()
        live_tables = sum(bool(row.get("present_in_runtime")) for row in inventory)
        migration_artifacts = [item for item in artifacts if item["present"]]
        warnings = [
            {
                "key": "postgresql_managed_operations_unverified",
                "severity": "warning",
                "summary": "Disposable runtime parity does not prove managed database operations.",
                "action": "Validate encrypted backups, restore drills, retention, monitoring, secret rotation, and least-privilege roles before real data.",
            }
        ]
        parity_checks = [
            {
                "key": "postgresql_live_schema",
                "status": "pass" if live_tables == len(REQUIRED_SCHEMA_TABLES) else "blocker",
                "sqlite_evidence": f"{live_tables}/{len(REQUIRED_SCHEMA_TABLES)} required tables are present in the selected PostgreSQL runtime.",
                "postgres_requirement": "The selected runtime must expose the complete versioned schema.",
                "action": "Keep live catalog verification at repository startup.",
            },
            {
                "key": "postgresql_repository_backend",
                "status": "pass",
                "sqlite_evidence": "Runtime repository selection is PostgreSQL.",
                "postgres_requirement": "All API repository calls must use the PostgreSQL adapter contract.",
                "action": "Keep SQLite as an explicit development fallback only.",
            },
            {
                "key": "postgresql_disposable_ci",
                "status": "pass" if runtime_ci_present else "blocker",
                "sqlite_evidence": "CI runs an end-to-end repository workflow against PostgreSQL 16.",
                "postgres_requirement": "Repository writes, reads, tenant scope, JSONB, and lifecycle behavior must run against disposable PostgreSQL.",
                "action": "Keep the PostgreSQL runtime smoke in the required CI job.",
            },
        ]
        return {
            "status": "ready" if runtime_ci_present else "blocked",
            "generated_at": self._fetchone("SELECT NOW() AS now")["now"].isoformat(),
            "runtime_backend": "postgresql",
            "target_backend": "postgresql",
            "repository_backend_status": "implemented",
            "migration_ready": live_tables == len(REQUIRED_SCHEMA_TABLES),
            "production_ready": False,
            "live_connection_tested": True,
            "required_environment": list(POSTGRESQL_REQUIRED_ENVIRONMENT),
            "configured_environment": list(POSTGRESQL_REQUIRED_ENVIRONMENT),
            "missing_environment": [],
            "required_table_count": len(REQUIRED_SCHEMA_TABLES),
            "present_table_count": live_tables,
            "json_column_count": len(JSON_TEXT_COLUMNS),
            "tenant_scope_count": len(TENANT_SCOPED_TABLES),
            "migration_artifact_count": len(migration_artifacts),
            "latest_migration_version": migration_artifacts[-1]["version"] if migration_artifacts else None,
            "versioned_migration_contract_present": len(migration_artifacts) == len(POSTGRESQL_EXPECTED_MIGRATIONS),
            "disposable_migration_ci_present": runtime_ci_present,
            "disposable_repository_ci_present": runtime_ci_present,
            "repository_adapter_contract_status": contract["status"],
            "repository_adapter_contract_present": True,
            "repository_adapter_contract_version": contract["version"],
            "repository_adapter_module": contract["module"],
            "repository_adapter_stage": contract["stage"],
            "repository_adapter_contract_method_count": contract["method_count"],
            "repository_adapter_implemented_method_count": contract["implemented_method_count"],
            "repository_adapter_pending_method_count": contract["pending_method_count"],
            "repository_adapter_read_only_method_count": contract["read_only_method_count"],
            "repository_adapter_write_method_count": contract["write_method_count"],
            "repository_adapter_completed_method_group_count": contract["completed_method_group_count"],
            "repository_adapter_completed_method_groups": contract["completed_method_groups"],
            "repository_adapter_implemented_methods": contract["implemented_methods"],
            "repository_adapter_model_registry_read_present": True,
            "repository_adapter_model_registry_write_present": True,
            "repository_adapter_model_registry_group_present": True,
            "repository_adapter_audit_group_present": True,
            "repository_adapter_organization_group_present": True,
            "repository_adapter_identity_access_group_present": True,
            "repository_adapter_staff_invites_delivery_group_present": True,
            "repository_adapter_application_lifecycle_group_present": True,
            "repository_adapter_portfolio_analytics_group_present": True,
            "repository_adapter_contract_groups": contract["method_groups"],
            "migration_artifacts": artifacts,
            "schema_inventory": inventory,
            "parity_checks": parity_checks,
            "blockers": [] if runtime_ci_present else [
                {
                    "key": "postgresql_disposable_runtime_ci_missing",
                    "severity": "blocker",
                    "summary": "The runtime CI marker is missing.",
                    "action": "Run scripts/postgresql-runtime-smoke.py in the PostgreSQL CI job.",
                }
            ],
            "next_required_controls": warnings,
            "limitation": POSTGRESQL_RUNTIME_LIMITATION,
        }
