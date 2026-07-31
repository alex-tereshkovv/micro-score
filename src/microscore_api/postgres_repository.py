"""PostgreSQL repository adapter contract and completed method groups.

This module is deliberately not a production backend yet. It records the
repository method families that a future PostgreSQL implementation must support
before ``MICROSCORE_STORAGE_BACKEND=postgresql`` can be enabled, and it exposes
the first executable method groups for repository parity tests.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from typing import Any, NoReturn


POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION = "postgresql-repository-adapter-v6"
POSTGRESQL_REPOSITORY_ADAPTER_MODULE = "microscore_api.postgres_repository"
POSTGRESQL_REPOSITORY_ADAPTER_STATUS = "partial_method_groups"
POSTGRESQL_REPOSITORY_ADAPTER_STAGE = "model_registry_audit_organizations_identity_groups_v1"
DEFAULT_SESSION_TTL_HOURS = 8.0
STAFF_ROLES = {"admin", "mfi_analyst"}
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
POSTGRESQL_AUDIT_READ_METHODS = ("list_audit_events",)
POSTGRESQL_AUDIT_WRITE_METHODS = ("record_audit_event",)
POSTGRESQL_AUDIT_METHODS = (
    "record_audit_event",
    "list_audit_events",
)
POSTGRESQL_ORGANIZATION_READ_METHODS = (
    "get_organization",
    "list_organizations",
)
POSTGRESQL_ORGANIZATION_WRITE_METHODS = (
    "create_organization",
    "assign_user_organization",
)
POSTGRESQL_ORGANIZATION_METHODS = (
    "create_organization",
    "get_organization",
    "list_organizations",
    "assign_user_organization",
)
POSTGRESQL_IDENTITY_READ_METHODS = (
    "get_user",
    "list_users",
    "get_user_by_token",
    "list_active_sessions",
)
POSTGRESQL_IDENTITY_WRITE_METHODS = (
    "create_user",
    "disable_user",
    "reactivate_user",
    "attest_user_mfa",
    "create_session",
    "revoke_session",
    "revoke_session_by_id",
)
POSTGRESQL_IDENTITY_METHODS = (
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
)
POSTGRESQL_REPOSITORY_IMPLEMENTED_METHODS = (
    *POSTGRESQL_MODEL_REGISTRY_METHODS,
    *POSTGRESQL_AUDIT_METHODS,
    *POSTGRESQL_ORGANIZATION_METHODS,
    *POSTGRESQL_IDENTITY_METHODS,
)
POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION = (
    "PostgreSQL Repository Adapter v6 implements the model registry, audit, "
    "organization, and identity/session method groups through an injected "
    "DB-API compatible connection factory. Runtime backend selection remains "
    "disabled until tenant-scoped application, invite, simulation, and analytics flows have "
    "repository parity coverage."
)
USER_COLUMNS = (
    "email",
    "password_hash",
    "role",
    "organization_id",
    "created_at",
    "disabled_at",
    "disabled_by",
    "mfa_attested_at",
    "mfa_attested_by",
    "mfa_method",
)
LIST_USER_COLUMNS = (
    "email",
    "role",
    "organization_id",
    "created_at",
    "disabled_at",
    "disabled_by",
    "mfa_attested_at",
    "mfa_attested_by",
    "mfa_method",
)
SESSION_USER_COLUMNS = (
    *USER_COLUMNS,
    "session_created_at",
)
ACTIVE_SESSION_COLUMNS = (
    "token",
    "email",
    "session_created_at",
    "role",
    "organization_id",
    "disabled_at",
)
USER_SELECT = """
SELECT
    email,
    password_hash,
    role,
    organization_id,
    created_at,
    disabled_at,
    disabled_by,
    mfa_attested_at,
    mfa_attested_by,
    mfa_method
FROM users
"""
GET_USER_SQL = USER_SELECT + "WHERE email = %(email)s"
LIST_USERS_SQL = """
SELECT
    email,
    role,
    organization_id,
    created_at,
    disabled_at,
    disabled_by,
    mfa_attested_at,
    mfa_attested_by,
    mfa_method
FROM users
ORDER BY role, email
"""
CREATE_USER_SQL = """
INSERT INTO users (
    email,
    password_hash,
    role,
    organization_id,
    created_at
)
VALUES (
    %(email)s,
    %(password_hash)s,
    %(role)s,
    %(organization_id)s,
    %(created_at)s
)
"""
GET_USER_DISABLE_STATUS_SQL = """
SELECT email, disabled_at
FROM users
WHERE email = %(email)s
"""
DISABLE_USER_SQL = """
UPDATE users
SET disabled_at = %(disabled_at)s, disabled_by = %(disabled_by)s
WHERE email = %(email)s AND disabled_at IS NULL
"""
GET_USER_REACTIVATE_STATUS_SQL = """
SELECT email, disabled_at, disabled_by
FROM users
WHERE email = %(email)s
"""
REACTIVATE_USER_SQL = """
UPDATE users
SET disabled_at = NULL, disabled_by = NULL
WHERE email = %(email)s AND disabled_at IS NOT NULL
"""
GET_USER_MFA_STATUS_SQL = """
SELECT email, mfa_attested_at
FROM users
WHERE email = %(email)s
"""
ATTEST_USER_MFA_SQL = """
UPDATE users
SET
    mfa_attested_at = %(mfa_attested_at)s,
    mfa_attested_by = %(mfa_attested_by)s,
    mfa_method = %(mfa_method)s
WHERE email = %(email)s AND mfa_attested_at IS NULL
"""
CREATE_SESSION_SQL = """
INSERT INTO sessions (token, email, created_at)
VALUES (%(token)s, %(email)s, %(created_at)s)
"""
GET_USER_BY_TOKEN_SQL = """
SELECT
    users.email,
    users.password_hash,
    users.role,
    users.organization_id,
    users.created_at,
    users.disabled_at,
    users.disabled_by,
    users.mfa_attested_at,
    users.mfa_attested_by,
    users.mfa_method,
    sessions.created_at AS session_created_at
FROM sessions
JOIN users ON users.email = sessions.email
WHERE sessions.token = %(token)s
"""
DELETE_SESSION_BY_TOKEN_SQL = """
DELETE FROM sessions
WHERE token = %(token)s
"""
DELETE_SESSIONS_BY_EMAIL_SQL = """
DELETE FROM sessions
WHERE email = %(email)s
"""
LIST_ACTIVE_SESSIONS_SQL = """
SELECT
    sessions.token,
    sessions.email,
    sessions.created_at AS session_created_at,
    users.role,
    users.organization_id,
    users.disabled_at
FROM sessions
JOIN users ON users.email = sessions.email
ORDER BY sessions.created_at DESC
"""
ORGANIZATION_COLUMNS = (
    "id",
    "name",
    "region",
    "created_at",
)
ORGANIZATION_SELECT = """
SELECT
    id,
    name,
    region,
    created_at
FROM mfi_organizations
"""
GET_ORGANIZATION_SQL = ORGANIZATION_SELECT + "WHERE id = %(organization_id)s"
LIST_ORGANIZATIONS_SQL = (
    ORGANIZATION_SELECT
    + """
ORDER BY name
"""
)
CREATE_ORGANIZATION_SQL = """
INSERT INTO mfi_organizations (
    id,
    name,
    region,
    created_at
)
VALUES (
    %(organization_id)s,
    %(name)s,
    %(region)s,
    %(created_at)s
)
"""
ASSIGN_USER_ORGANIZATION_SQL = """
UPDATE users
SET organization_id = %(organization_id)s
WHERE email = %(email)s
"""
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
AUDIT_EVENT_COLUMNS = (
    "id",
    "actor_email",
    "action",
    "entity_type",
    "entity_id",
    "details_json",
    "created_at",
)
AUDIT_EVENT_SELECT = """
SELECT
    id,
    actor_email,
    action,
    entity_type,
    entity_id,
    details_json,
    created_at
FROM audit_events
"""
LIST_AUDIT_EVENTS_SQL = (
    AUDIT_EVENT_SELECT
    + """
ORDER BY id DESC
"""
)
RECORD_AUDIT_EVENT_SQL = """
INSERT INTO audit_events (
    actor_email,
    action,
    entity_type,
    entity_id,
    details_json,
    created_at
)
VALUES (
    %(actor_email)s,
    %(action)s,
    %(entity_type)s,
    %(entity_id)s,
    %(details_json)s::jsonb,
    %(created_at)s
)
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
    read_only_methods = (
        *POSTGRESQL_MODEL_REGISTRY_READ_METHODS,
        *POSTGRESQL_AUDIT_READ_METHODS,
        *POSTGRESQL_ORGANIZATION_READ_METHODS,
        *POSTGRESQL_IDENTITY_READ_METHODS,
    )
    write_methods = (
        *POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS,
        *POSTGRESQL_AUDIT_WRITE_METHODS,
        *POSTGRESQL_ORGANIZATION_WRITE_METHODS,
        *POSTGRESQL_IDENTITY_WRITE_METHODS,
    )
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
        "read_only_method_count": len(read_only_methods),
        "read_only_methods": list(read_only_methods),
        "write_method_count": len(write_methods),
        "write_methods": list(write_methods),
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


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def configured_session_ttl_hours() -> float:
    raw_value = os.environ.get("MICROSCORE_SESSION_TTL_HOURS", "").strip()
    if not raw_value:
        return DEFAULT_SESSION_TTL_HOURS
    try:
        value = float(raw_value)
    except ValueError:
        return DEFAULT_SESSION_TTL_HOURS
    return value if value > 0 else DEFAULT_SESSION_TTL_HOURS


def session_expiry_metadata(
    created_at: str | None = None,
    *,
    ttl_hours: float | None = None,
) -> dict[str, Any]:
    session_created_at = (
        _parse_utc_datetime(created_at) if created_at else datetime.now(timezone.utc)
    )
    ttl = ttl_hours if ttl_hours is not None else configured_session_ttl_hours()
    expires_at = session_created_at + timedelta(hours=ttl)
    return {
        "session_created_at": session_created_at.isoformat(),
        "session_expires_at": expires_at.isoformat(),
        "session_ttl_seconds": max(1, int(round(ttl * 3600))),
    }


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


def postgres_audit_event_from_row(row: object) -> dict[str, Any]:
    event = _row_to_mapping(row, AUDIT_EVENT_COLUMNS)
    event["details"] = _coerce_json(event.pop("details_json"), {}) or {}
    return event


def postgres_organization_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, ORGANIZATION_COLUMNS)


def postgres_user_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, USER_COLUMNS)


def postgres_list_user_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, LIST_USER_COLUMNS)


def postgres_session_user_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, SESSION_USER_COLUMNS)


def postgres_active_session_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, ACTIVE_SESSION_COLUMNS)


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


def audit_method_group_parity_snapshot(repository: object) -> dict[str, object]:
    events = getattr(repository, "list_audit_events")()
    return {
        "method_group": "audit",
        "implemented_methods": list(POSTGRESQL_AUDIT_METHODS),
        "event_count": len(events),
        "actions": [event["action"] for event in events],
        "entities": [
            f"{event['entity_type']}:{event.get('entity_id') or ''}"
            for event in events
        ],
        "details_keys": [
            sorted((event.get("details") or {}).keys())
            for event in events
        ],
        "method_group_complete": True,
    }


def _organization_identity(organization: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if organization is None:
        return None
    return {
        "id": organization["id"],
        "name": organization["name"],
        "region": organization["region"],
    }


def organization_method_group_parity_snapshot(repository: object) -> dict[str, object]:
    organizations = getattr(repository, "list_organizations")()
    lookups = [
        getattr(repository, "get_organization")(organization["id"])
        for organization in organizations
    ]
    return {
        "method_group": "organizations",
        "implemented_methods": list(POSTGRESQL_ORGANIZATION_METHODS),
        "organization_count": len(organizations),
        "organization_ids": [organization["id"] for organization in organizations],
        "organization_names": [organization["name"] for organization in organizations],
        "organization_regions": [
            organization["region"] for organization in organizations
        ],
        "lookup_matches": [
            _organization_identity(lookup) == _organization_identity(organization)
            for lookup, organization in zip(lookups, organizations)
        ],
        "method_group_complete": True,
    }


def identity_access_method_group_parity_snapshot(
    repository: object,
    *,
    now: datetime | None = None,
    ttl_hours: float | None = None,
) -> dict[str, object]:
    users = getattr(repository, "list_users")()
    active_sessions = getattr(repository, "list_active_sessions")(
        now=now,
        ttl_hours=ttl_hours,
    )
    staff_sessions = getattr(repository, "list_active_sessions")(
        staff_only=True,
        now=now,
        ttl_hours=ttl_hours,
    )
    return {
        "method_group": "identity_access",
        "implemented_methods": list(POSTGRESQL_IDENTITY_METHODS),
        "user_count": len(users),
        "user_emails": [user["email"] for user in users],
        "user_roles": [user["role"] for user in users],
        "user_organization_ids": [user.get("organization_id") for user in users],
        "disabled_users": [
            user["email"] for user in users if user.get("disabled_at") is not None
        ],
        "mfa_attested_users": [
            user["email"] for user in users if user.get("mfa_attested_at") is not None
        ],
        "active_session_count": len(active_sessions),
        "active_session_emails": [
            session["email"] for session in active_sessions
        ],
        "active_session_ids": [
            session["session_id"] for session in active_sessions
        ],
        "staff_session_count": len(staff_sessions),
        "staff_session_emails": [
            session["email"] for session in staff_sessions
        ],
        "method_group_complete": True,
    }


class PostgresRepositoryAdapter:
    """Partial PostgreSQL adapter for completed method-group parity tests.

    The adapter intentionally accepts an injected connection factory rather than
    opening ``MICROSCORE_DATABASE_URL`` by itself. That keeps the production
    backend disabled while still letting parity tests execute the first
    repository method groups.
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
        self._write_with_rowcounts(statements)

    def _write_with_rowcounts(
        self,
        statements: list[tuple[str, dict[str, object]]],
    ) -> list[int]:
        rowcounts: list[int] = []
        with self._connection() as connection:
            try:
                for sql, params in statements:
                    cursor = self._execute(connection, sql, params)
                    rowcounts.append(int(getattr(cursor, "rowcount", 0) or 0))
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
        return rowcounts

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_USER_SQL,
                    {
                        "email": email,
                        "password_hash": password_hash,
                        "role": role,
                        "organization_id": organization_id,
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        self.record_audit_event(
            actor_email=email,
            action="user_registered",
            entity_type="user",
            entity_id=email,
            details={"role": role, "organization_id": organization_id},
        )
        return self.get_user(email) or {}

    def get_user(self, email: str) -> dict[str, Any] | None:
        row = self._fetchone(GET_USER_SQL, {"email": email})
        return postgres_user_from_row(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        return [
            postgres_list_user_from_row(row)
            for row in self._fetchall(LIST_USERS_SQL)
        ]

    def disable_user(self, email: str, disabled_by: str) -> dict[str, Any] | None:
        existing = self._fetchone(GET_USER_DISABLE_STATUS_SQL, {"email": email})
        if existing is None:
            return None
        existing_status = _row_to_mapping(existing, ("email", "disabled_at"))
        if existing_status["disabled_at"] is None:
            self._write(
                [
                    (
                        DISABLE_USER_SQL,
                        {
                            "email": email,
                            "disabled_at": _now_iso(),
                            "disabled_by": disabled_by,
                        },
                    )
                ]
            )
        revoked_counts = self._write_with_rowcounts(
            [(DELETE_SESSIONS_BY_EMAIL_SQL, {"email": email})]
        )
        disabled = self.get_user(email) or {}
        disabled["revoked_session_count"] = revoked_counts[0] if revoked_counts else 0
        disabled["was_already_disabled"] = (
            existing_status["disabled_at"] is not None
        )
        return disabled

    def reactivate_user(self, email: str) -> dict[str, Any] | None:
        existing = self._fetchone(GET_USER_REACTIVATE_STATUS_SQL, {"email": email})
        if existing is None:
            return None
        existing_status = _row_to_mapping(
            existing,
            ("email", "disabled_at", "disabled_by"),
        )
        if existing_status["disabled_at"] is not None:
            self._write([(REACTIVATE_USER_SQL, {"email": email})])
        reactivated = self.get_user(email) or {}
        reactivated["was_already_active"] = existing_status["disabled_at"] is None
        reactivated["previous_disabled_at"] = existing_status["disabled_at"]
        reactivated["previous_disabled_by"] = existing_status["disabled_by"]
        return reactivated

    def attest_user_mfa(
        self,
        email: str,
        attested_by: str,
        method: str,
    ) -> dict[str, Any] | None:
        existing = self._fetchone(GET_USER_MFA_STATUS_SQL, {"email": email})
        if existing is None:
            return None
        existing_status = _row_to_mapping(existing, ("email", "mfa_attested_at"))
        if existing_status["mfa_attested_at"] is None:
            self._write(
                [
                    (
                        ATTEST_USER_MFA_SQL,
                        {
                            "email": email,
                            "mfa_attested_at": _now_iso(),
                            "mfa_attested_by": attested_by,
                            "mfa_method": method,
                        },
                    )
                ]
            )
        attested = self.get_user(email) or {}
        attested["was_already_attested"] = (
            existing_status["mfa_attested_at"] is not None
        )
        return attested

    def create_session(
        self,
        token: str,
        email: str,
        *,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        stored_created_at = created_at or _now_iso()
        self._write(
            [
                (
                    CREATE_SESSION_SQL,
                    {
                        "token": token,
                        "email": email,
                        "created_at": stored_created_at,
                    },
                )
            ]
        )
        return session_expiry_metadata(stored_created_at)

    def get_user_by_token(
        self,
        token: str,
        *,
        now: datetime | None = None,
        ttl_hours: float | None = None,
    ) -> dict[str, Any] | None:
        row = self._fetchone(GET_USER_BY_TOKEN_SQL, {"token": token})
        if row is None:
            return None
        user = postgres_session_user_from_row(row)
        if user["disabled_at"] is not None:
            self.revoke_session(token)
            return None
        metadata = session_expiry_metadata(
            user["session_created_at"],
            ttl_hours=ttl_hours,
        )
        expires_at = _parse_utc_datetime(metadata["session_expires_at"])
        if expires_at <= (now or datetime.now(timezone.utc)):
            self.revoke_session(token)
            return None
        user.update(metadata)
        return user

    def revoke_session(self, token: str) -> bool:
        rowcounts = self._write_with_rowcounts(
            [(DELETE_SESSION_BY_TOKEN_SQL, {"token": token})]
        )
        return bool(rowcounts and rowcounts[0] > 0)

    def list_active_sessions(
        self,
        *,
        staff_only: bool = False,
        now: datetime | None = None,
        ttl_hours: float | None = None,
    ) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        rows = self._fetchall(LIST_ACTIVE_SESSIONS_SQL)
        active_sessions: list[dict[str, Any]] = []
        expired_or_disabled_tokens: list[str] = []
        for row in rows:
            session = postgres_active_session_from_row(row)
            if session["disabled_at"] is not None:
                expired_or_disabled_tokens.append(str(session["token"]))
                continue
            if staff_only and session["role"] not in STAFF_ROLES:
                continue
            metadata = session_expiry_metadata(
                session["session_created_at"],
                ttl_hours=ttl_hours,
            )
            expires_at = _parse_utc_datetime(metadata["session_expires_at"])
            if expires_at <= now:
                expired_or_disabled_tokens.append(str(session["token"]))
                continue
            session.update(metadata)
            session["session_id"] = hashlib.sha256(
                str(session["token"]).encode("utf-8")
            ).hexdigest()
            active_sessions.append(session)

        for token in expired_or_disabled_tokens:
            self.revoke_session(token)
        return active_sessions

    def revoke_session_by_id(
        self,
        session_id: str,
        *,
        staff_only: bool = False,
    ) -> dict[str, Any] | None:
        normalized_session_id = session_id.strip().lower()
        for session in self.list_active_sessions(staff_only=staff_only):
            if session["session_id"] != normalized_session_id:
                continue
            if self.revoke_session(str(session["token"])):
                return session
            return None
        return None

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

    def record_audit_event(
        self,
        *,
        actor_email: str | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, Any],
    ) -> None:
        self._write(
            [
                (
                    RECORD_AUDIT_EVENT_SQL,
                    {
                        "actor_email": actor_email,
                        "action": action,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "details_json": _json_dumps(details),
                        "created_at": _now_iso(),
                    },
                )
            ]
        )

    def list_audit_events(self) -> list[dict[str, Any]]:
        return [
            postgres_audit_event_from_row(row)
            for row in self._fetchall(LIST_AUDIT_EVENTS_SQL)
        ]

    def create_organization(
        self,
        *,
        organization_id: str,
        name: str,
        region: str,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_ORGANIZATION_SQL,
                    {
                        "organization_id": organization_id,
                        "name": name,
                        "region": region,
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        return self.get_organization(organization_id) or {}

    def get_organization(self, organization_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            GET_ORGANIZATION_SQL,
            {"organization_id": organization_id},
        )
        return postgres_organization_from_row(row) if row else None

    def list_organizations(self) -> list[dict[str, Any]]:
        return [
            postgres_organization_from_row(row)
            for row in self._fetchall(LIST_ORGANIZATIONS_SQL)
        ]

    def assign_user_organization(
        self,
        email: str,
        organization_id: str | None,
    ) -> None:
        self._write(
            [
                (
                    ASSIGN_USER_ORGANIZATION_SQL,
                    {
                        "email": email,
                        "organization_id": organization_id,
                    },
                )
            ]
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
