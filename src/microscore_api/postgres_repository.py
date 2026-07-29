"""PostgreSQL repository adapter contract and first completed method group.

This module is deliberately not a production backend yet. It records the
repository method families that a future PostgreSQL implementation must support
before ``MICROSCORE_STORAGE_BACKEND=postgresql`` can be enabled, and it exposes
the first executable method group for model-registry parity tests.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, NoReturn


POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION = "postgresql-repository-adapter-v3"
POSTGRESQL_REPOSITORY_ADAPTER_MODULE = "microscore_api.postgres_repository"
POSTGRESQL_REPOSITORY_ADAPTER_STATUS = "partial_method_group"
POSTGRESQL_REPOSITORY_ADAPTER_STAGE = "model_registry_method_group_v1"
POSTGRESQL_MODEL_REGISTRY_READ_METHODS = (
    "get_model_version",
    "get_active_model_version",
    "list_model_versions",
)
POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS = (
    "create_model_version",
    "activate_model_version",
)
POSTGRESQL_MODEL_REGISTRY_METHODS = (
    "create_model_version",
    "get_model_version",
    "get_active_model_version",
    "list_model_versions",
    "activate_model_version",
)
POSTGRESQL_REPOSITORY_IMPLEMENTED_METHODS = POSTGRESQL_MODEL_REGISTRY_METHODS
POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION = (
    "PostgreSQL Repository Adapter v3 implements the model registry method "
    "group through an injected DB-API compatible connection factory. Runtime "
    "backend selection remains disabled until identity, tenant-scoped "
    "application, invite, simulation, analytics, and audit flows have "
    "repository parity coverage."
)
MODEL_VERSION_COLUMNS = (
    "version",
    "model_name",
    "model_type",
    "lifecycle_status",
    "is_active",
    "feature_schema_version",
    "training_data_label",
    "random_state",
    "metrics_json",
    "limitations_json",
    "created_by",
    "created_at",
    "activated_at",
)
MODEL_VERSION_SELECT = """
SELECT
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
FROM model_versions
"""
GET_MODEL_VERSION_SQL = MODEL_VERSION_SELECT + "WHERE version = %(version)s"
GET_MODEL_VERSION_EXISTS_SQL = """
SELECT version
FROM model_versions
WHERE version = %(version)s
"""
GET_ACTIVE_MODEL_VERSION_SQL = (
    MODEL_VERSION_SELECT
    + """
WHERE is_active IS TRUE
ORDER BY activated_at DESC NULLS LAST, created_at DESC, version DESC
LIMIT 1
"""
)
LIST_MODEL_VERSIONS_SQL = (
    MODEL_VERSION_SELECT
    + """
ORDER BY is_active DESC, created_at DESC, version DESC
"""
)
CREATE_MODEL_VERSION_SQL = """
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
    %(version)s,
    %(model_name)s,
    'logistic_regression',
    'candidate',
    FALSE,
    %(feature_schema_version)s,
    %(training_data_label)s,
    %(random_state)s,
    %(metrics_json)s::jsonb,
    %(limitations_json)s::jsonb,
    %(created_by)s,
    %(created_at)s,
    NULL
)
"""
DEACTIVATE_OTHER_MODEL_VERSIONS_SQL = """
UPDATE model_versions
SET lifecycle_status = 'inactive', is_active = FALSE
WHERE is_active IS TRUE AND version <> %(version)s
"""
ACTIVATE_MODEL_VERSION_SQL = """
UPDATE model_versions
SET lifecycle_status = 'active', is_active = TRUE, activated_at = %(activated_at)s
WHERE version = %(version)s
"""


@dataclass(frozen=True)
class RepositoryMethodGroup:
    key: str
    label: str
    methods: tuple[str, ...]

    def as_dict(
        self,
        implemented_methods: tuple[str, ...] = (),
    ) -> dict[str, object]:
        implemented_method_set = set(implemented_methods)
        implemented = [
            method for method in self.methods if method in implemented_method_set
        ]
        pending = [
            method for method in self.methods if method not in implemented_method_set
        ]
        return {
            "key": self.key,
            "label": self.label,
            "method_count": len(self.methods),
            "methods": list(self.methods),
            "implemented_method_count": len(implemented),
            "implemented_methods": implemented,
            "pending_method_count": len(pending),
            "pending_methods": pending,
        }


REPOSITORY_METHOD_GROUPS: tuple[RepositoryMethodGroup, ...] = (
    RepositoryMethodGroup(
        key="identity_access",
        label="Identity, MFA, and session lifecycle",
        methods=(
            "create_user",
            "get_user",
            "list_users",
            "disable_user",
            "reactivate_user",
            "attest_user_mfa",
            "create_session",
            "get_user_by_token",
            "list_active_sessions",
            "revoke_session",
            "revoke_session_by_id",
        ),
    ),
    RepositoryMethodGroup(
        key="organizations",
        label="MFI organization and tenant assignment",
        methods=(
            "create_organization",
            "get_organization",
            "list_organizations",
            "assign_user_organization",
        ),
    ),
    RepositoryMethodGroup(
        key="staff_invites_delivery",
        label="Staff invites, delivery outbox, worker, and webhooks",
        methods=(
            "create_staff_invite",
            "get_staff_invite",
            "list_staff_invites",
            "mark_staff_invite_accepted",
            "mark_staff_invite_revoked",
            "mark_staff_invite_delivered",
            "record_staff_invite_delivery_attempt",
            "record_staff_invite_delivery_event",
            "get_staff_invite_delivery_attempt",
            "get_staff_invite_delivery_event",
            "list_staff_invite_delivery_attempts",
            "list_staff_invite_delivery_events",
            "list_staff_invite_delivery_outbox_attempts",
            "update_staff_invite_delivery_attempt_status",
            "update_staff_invite_delivery_worker_state",
        ),
    ),
    RepositoryMethodGroup(
        key="application_lifecycle",
        label="Borrower application lifecycle, scoring, review, and decisions",
        methods=(
            "create_application",
            "get_application",
            "list_applications",
            "list_borrower_applications",
            "assign_application_organization",
            "update_application_score",
            "record_application_decision",
            "list_application_decisions",
            "list_application_timeline",
            "clear_applications",
        ),
    ),
    RepositoryMethodGroup(
        key="model_registry",
        label="Model registry and active-version governance",
        methods=(
            "create_model_version",
            "get_model_version",
            "get_active_model_version",
            "list_model_versions",
            "activate_model_version",
        ),
    ),
    RepositoryMethodGroup(
        key="portfolio_analytics",
        label="Portfolio simulations and MFI analytics",
        methods=(
            "create_portfolio_simulation",
            "get_portfolio_simulation",
            "list_portfolio_simulations",
            "segment_analytics",
            "decision_analytics",
        ),
    ),
    RepositoryMethodGroup(
        key="audit",
        label="Audit event recording and review",
        methods=(
            "record_audit_event",
            "list_audit_events",
        ),
    ),
)


def repository_contract_methods() -> tuple[str, ...]:
    return tuple(
        method
        for group in REPOSITORY_METHOD_GROUPS
        for method in group.methods
    )


def repository_implemented_methods() -> tuple[str, ...]:
    return POSTGRESQL_REPOSITORY_IMPLEMENTED_METHODS


def repository_contract_summary() -> dict[str, object]:
    methods = repository_contract_methods()
    implemented_methods = repository_implemented_methods()
    completed_groups = [
        group.key
        for group in REPOSITORY_METHOD_GROUPS
        if all(method in implemented_methods for method in group.methods)
    ]
    return {
        "module": POSTGRESQL_REPOSITORY_ADAPTER_MODULE,
        "version": POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        "status": POSTGRESQL_REPOSITORY_ADAPTER_STATUS,
        "stage": POSTGRESQL_REPOSITORY_ADAPTER_STAGE,
        "present": True,
        "runtime_enabled": False,
        "method_count": len(methods),
        "implemented_method_count": len(implemented_methods),
        "implemented_methods": list(implemented_methods),
        "pending_method_count": len(methods) - len(implemented_methods),
        "completed_method_group_count": len(completed_groups),
        "completed_method_groups": completed_groups,
        "read_only_method_count": len(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "read_only_methods": list(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "write_method_count": len(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS),
        "write_methods": list(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS),
        "method_groups": [
            group.as_dict(implemented_methods)
            for group in REPOSITORY_METHOD_GROUPS
        ],
        "limitation": POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION,
    }


def _coerce_json(value: object, fallback: object) -> object:
    if value is None:
        return fallback
    if isinstance(value, str):
        return json.loads(value)
    return value


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "t", "true", "yes", "y"}
    return bool(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_mapping(
    row: object,
    columns: tuple[str, ...] = MODEL_VERSION_COLUMNS,
) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "keys") and hasattr(row, "__getitem__"):
        return {str(key): row[key] for key in row.keys()}
    if isinstance(row, tuple):
        return dict(zip(columns, row))
    if isinstance(row, list):
        return dict(zip(columns, row))
    raise TypeError(f"Unsupported PostgreSQL row type: {type(row).__name__}")


def postgres_model_version_from_row(row: object) -> dict[str, Any]:
    model_version = _row_to_mapping(row)
    model_version["is_active"] = _coerce_bool(model_version["is_active"])
    model_version["metrics"] = (
        _coerce_json(model_version.pop("metrics_json"), {}) or {}
    )
    model_version["limitations"] = (
        _coerce_json(model_version.pop("limitations_json"), []) or []
    )
    return model_version


def model_registry_read_parity_snapshot(repository: object) -> dict[str, object]:
    versions = getattr(repository, "list_model_versions")()
    active = getattr(repository, "get_active_model_version")()
    active_lookup = None
    if active:
        active_lookup = getattr(repository, "get_model_version")(active["version"])
    return {
        "method_group": "model_registry",
        "implemented_methods": list(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "version_count": len(versions),
        "versions": [row["version"] for row in versions],
        "active_version": active["version"] if active else None,
        "active_is_marked": bool(active and active.get("is_active")),
        "active_lookup_matches": active == active_lookup if active else active_lookup is None,
    }


def model_registry_method_group_parity_snapshot(repository: object) -> dict[str, object]:
    snapshot = model_registry_read_parity_snapshot(repository)
    snapshot["implemented_methods"] = list(POSTGRESQL_MODEL_REGISTRY_METHODS)
    snapshot["write_methods"] = list(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS)
    snapshot["method_group_complete"] = True
    return snapshot


class PostgresRepositoryAdapter:
    """Partial PostgreSQL adapter for model registry parity tests.

    The adapter intentionally accepts an injected connection factory rather than
    opening ``MICROSCORE_DATABASE_URL`` by itself. That keeps the production
    backend disabled while still letting parity tests execute the first
    repository method group.
    """

    def __init__(self, connection_factory: Callable[[], Any] | None = None) -> None:
        self._connection_factory = connection_factory

    @property
    def backend(self) -> str:
        return "postgresql"

    def describe_contract(self) -> dict[str, object]:
        return {
            **repository_contract_summary(),
            "backend": self.backend,
            "database_url_env": "MICROSCORE_DATABASE_URL",
        }

    @contextmanager
    def _connection(self) -> Any:
        if self._connection_factory is None:
            raise RuntimeError(
                "PostgreSQL repository adapter requires an injected "
                "connection_factory for parity tests. Runtime backend selection "
                "is still disabled."
            )
        connection = self._connection_factory()
        try:
            yield connection
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _execute(connection: object, sql: str, params: dict[str, object]) -> object:
        execute = getattr(connection, "execute", None)
        if callable(execute):
            return execute(sql, params)
        cursor = connection.cursor()
        cursor.execute(sql, params)
        return cursor

    def _fetchone(
        self,
        sql: str,
        params: dict[str, object] | None = None,
    ) -> object | None:
        with self._connection() as connection:
            cursor = self._execute(connection, sql, params or {})
            try:
                return cursor.fetchone()
            finally:
                close = getattr(cursor, "close", None)
                if callable(close):
                    close()

    def _fetchall(
        self,
        sql: str,
        params: dict[str, object] | None = None,
    ) -> list[object]:
        with self._connection() as connection:
            cursor = self._execute(connection, sql, params or {})
            try:
                return list(cursor.fetchall())
            finally:
                close = getattr(cursor, "close", None)
                if callable(close):
                    close()

    def _write(
        self,
        statements: list[tuple[str, dict[str, object]]],
    ) -> None:
        with self._connection() as connection:
            try:
                for sql, params in statements:
                    cursor = self._execute(connection, sql, params)
                    close = getattr(cursor, "close", None)
                    if callable(close):
                        close()
                commit = getattr(connection, "commit", None)
                if callable(commit):
                    commit()
            except Exception:
                rollback = getattr(connection, "rollback", None)
                if callable(rollback):
                    rollback()
                raise

    def get_model_version(self, version: str) -> dict[str, Any] | None:
        row = self._fetchone(GET_MODEL_VERSION_SQL, {"version": version})
        return postgres_model_version_from_row(row) if row else None

    def get_active_model_version(self) -> dict[str, Any] | None:
        row = self._fetchone(GET_ACTIVE_MODEL_VERSION_SQL)
        return postgres_model_version_from_row(row) if row else None

    def list_model_versions(self) -> list[dict[str, Any]]:
        return [
            postgres_model_version_from_row(row)
            for row in self._fetchall(LIST_MODEL_VERSIONS_SQL)
        ]

    def create_model_version(
        self,
        *,
        version: str,
        model_name: str,
        feature_schema_version: str,
        training_data_label: str,
        random_state: int,
        metrics: dict[str, Any],
        limitations: list[str],
        created_by: str,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_MODEL_VERSION_SQL,
                    {
                        "version": version,
                        "model_name": model_name,
                        "feature_schema_version": feature_schema_version,
                        "training_data_label": training_data_label,
                        "random_state": random_state,
                        "metrics_json": _json_dumps(metrics),
                        "limitations_json": _json_dumps(limitations),
                        "created_by": created_by,
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        return self.get_model_version(version) or {}

    def activate_model_version(self, version: str) -> dict[str, Any] | None:
        if self._fetchone(GET_MODEL_VERSION_EXISTS_SQL, {"version": version}) is None:
            return None
        self._write(
            [
                (DEACTIVATE_OTHER_MODEL_VERSIONS_SQL, {"version": version}),
                (
                    ACTIVATE_MODEL_VERSION_SQL,
                    {
                        "version": version,
                        "activated_at": _now_iso(),
                    },
                ),
            ]
        )
        return self.get_model_version(version)


@dataclass(frozen=True)
class PostgresRepositoryAdapterSkeleton:
    """Runtime guardrail that keeps backend selection disabled."""

    database_url_env: str = "MICROSCORE_DATABASE_URL"
    runtime_enabled: bool = False

    @property
    def backend(self) -> str:
        return "postgresql"

    def describe_contract(self) -> dict[str, object]:
        return {
            **repository_contract_summary(),
            "backend": self.backend,
            "database_url_env": self.database_url_env,
        }

    def connect(self) -> NoReturn:
        raise RuntimeError(
            "PostgreSQL repository adapter runtime is disabled. "
            "Use PostgresRepositoryAdapter with an injected connection_factory "
            "only in parity tests until production storage controls are implemented."
        )
