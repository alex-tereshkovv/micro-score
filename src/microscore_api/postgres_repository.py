"""PostgreSQL repository adapter contract and first read-only path.

This module is deliberately not a production backend yet. It records the
repository method families that a future PostgreSQL implementation must support
before ``MICROSCORE_STORAGE_BACKEND=postgresql`` can be enabled, and it exposes
the first executable read-only adapter path for model-registry parity tests.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import json
from typing import Any, NoReturn


POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION = "postgresql-repository-adapter-v2"
POSTGRESQL_REPOSITORY_ADAPTER_MODULE = "microscore_api.postgres_repository"
POSTGRESQL_REPOSITORY_ADAPTER_STATUS = "partial_read_only"
POSTGRESQL_REPOSITORY_ADAPTER_STAGE = "model_registry_read_path_v1"
POSTGRESQL_MODEL_REGISTRY_READ_METHODS = (
    "get_model_version",
    "get_active_model_version",
    "list_model_versions",
)
POSTGRESQL_REPOSITORY_IMPLEMENTED_METHODS = POSTGRESQL_MODEL_REGISTRY_READ_METHODS
POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION = (
    "PostgreSQL Repository Adapter v2 implements only the read-only model "
    "registry path through an injected DB-API compatible connection factory. "
    "Runtime backend selection remains disabled until write methods, tenant "
    "flows, and disposable PostgreSQL parity tests cover the full repository "
    "contract."
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
        "read_only_method_count": len(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "read_only_methods": list(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
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


class PostgresRepositoryAdapter:
    """Partial PostgreSQL adapter for read-only model registry parity tests.

    The adapter intentionally accepts an injected connection factory rather than
    opening ``MICROSCORE_DATABASE_URL`` by itself. That keeps the production
    backend disabled while still letting disposable PostgreSQL tests execute the
    first repository query path.
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

    def create_model_version(self, **_: object) -> NoReturn:
        raise NotImplementedError(
            "PostgreSQL adapter v2 implements read-only model registry methods only."
        )

    def activate_model_version(self, version: str) -> NoReturn:
        raise NotImplementedError(
            f"PostgreSQL adapter v2 cannot activate {version!r}; write methods "
            "are still pending full repository parity coverage."
        )


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
