"""SQLite persistence for the MicroScore API prototype."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
from typing import Any

from microscore.paths import PROJECT_ROOT

DEFAULT_API_DB_PATH = PROJECT_ROOT / "data" / "app" / "microscore.sqlite3"
DEFAULT_SESSION_TTL_HOURS = 8.0
DEFAULT_MODEL_VERSION = "research-v0.1"
DEFAULT_MODEL_NAME = "Logistic Regression"
DEFAULT_FEATURE_SCHEMA_VERSION = "behavioral-v1"
DEFAULT_TRAINING_DATA_LABEL = "synthetic-credit-risk-v1"
DEFAULT_MODEL_RANDOM_STATE = 42
DEFAULT_STORAGE_BACKEND = "sqlite"
SUPPORTED_STORAGE_BACKENDS = {DEFAULT_STORAGE_BACKEND}
POSTGRESQL_STORAGE_ALIASES = {"postgres", "postgresql"}
REQUIRED_SCHEMA_TABLES = (
    "mfi_organizations",
    "users",
    "sessions",
    "staff_invites",
    "staff_invite_delivery_attempts",
    "staff_invite_delivery_events",
    "loan_applications",
    "application_decisions",
    "audit_events",
    "model_versions",
    "portfolio_simulations",
)
JSON_TEXT_COLUMNS = (
    "loan_applications.behavioral_signals_json",
    "loan_applications.score_result_json",
    "audit_events.details_json",
    "model_versions.metrics_json",
    "model_versions.limitations_json",
    "portfolio_simulations.request_json",
    "portfolio_simulations.result_json",
    "staff_invite_delivery_events.metadata_json",
)
TENANT_SCOPED_TABLES = (
    "users.organization_id",
    "loan_applications.organization_id",
    "staff_invites.organization_id",
    "portfolio_simulations.organization_id",
)
POSTGRESQL_MIGRATION_CHECKLIST = (
    "Create managed PostgreSQL schema migrations before enabling a non-SQLite backend.",
    "Map JSON text columns to jsonb or an explicitly versioned text strategy.",
    "Preserve organization_id tenant scoping for queues, review packets, "
    "analytics, and simulations.",
    "Port session, staff invite, audit, model registry, and simulation "
    "repositories behind the same API.",
    "Run SQLite parity tests plus PostgreSQL integration tests against a disposable database.",
)


class DuplicateUserError(ValueError):
    """Raised when an email is already registered."""


class DuplicateOrganizationError(ValueError):
    """Raised when an organization id is already registered."""


class DuplicateModelVersionError(ValueError):
    """Raised when a model version is already registered."""


class InvalidApplicationTransitionError(ValueError):
    """Raised when an application lifecycle transition is not allowed."""


class UnsupportedStorageBackendError(ValueError):
    """Raised when configuration requests a repository backend not implemented yet."""


def default_database_path() -> Path:
    configured = os.environ.get("MICROSCORE_API_DB_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_API_DB_PATH


def configured_storage_backend() -> str:
    raw_value = os.environ.get("MICROSCORE_STORAGE_BACKEND", DEFAULT_STORAGE_BACKEND)
    backend = raw_value.strip().lower()
    if not backend:
        return DEFAULT_STORAGE_BACKEND
    if backend in {"sqlite", "sqlite3"}:
        return DEFAULT_STORAGE_BACKEND
    if backend in POSTGRESQL_STORAGE_ALIASES:
        return "postgresql"
    return backend


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _initial_delivery_worker_state(status: str, attempted_at: str) -> dict[str, Any]:
    if status == "queued":
        return {
            "worker_status": "queued",
            "worker_attempt_count": 0,
            "next_worker_run_at": attempted_at,
            "dead_letter_at": None,
            "last_worker_error": None,
        }
    return {
        "worker_status": "completed",
        "worker_attempt_count": 0,
        "next_worker_run_at": None,
        "dead_letter_at": None,
        "last_worker_error": None,
    }


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _json_loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


DECISION_VALUES = ("approve", "review", "decline")
DECISION_WORKFLOW_STATUSES = {
    "approve": "approved",
    "review": "under_review",
    "decline": "declined",
}
TERMINAL_APPLICATION_STATUSES = {"approved", "declined"}
DECISION_TRANSITIONS = {
    "scored": {"approve", "review", "decline"},
    "under_review": {"approve", "decline"},
}
PROXY_SENSITIVITY_THRESHOLD = 0.2


def _safe_rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return count / total


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _high_risk_probability(record: dict[str, Any]) -> float | None:
    score = record.get("score_result") or {}
    probability = score.get("high_risk_probability")
    if probability is None:
        return None
    return float(probability)


def _proxy_sensitivity_delta(record: dict[str, Any]) -> float | None:
    score = record.get("score_result") or {}
    delta = score.get("proxy_sensitivity_delta")
    if delta is None:
        return None
    return float(delta)


def _high_risk_probabilities(records: list[dict[str, Any]]) -> list[float]:
    return [
        probability
        for record in records
        if (probability := _high_risk_probability(record)) is not None
    ]


def _proxy_sensitivity_deltas(records: list[dict[str, Any]]) -> list[float]:
    return [
        delta
        for record in records
        if (delta := _proxy_sensitivity_delta(record)) is not None
    ]


def _proxy_sensitivity_bucket(record: dict[str, Any]) -> str:
    score = record.get("score_result") or {}
    delta = _proxy_sensitivity_delta(record)
    warnings = " ".join(score.get("warnings") or []).lower()
    if delta is None:
        return "not_recorded"
    if (
        delta >= PROXY_SENSITIVITY_THRESHOLD
        or "sensitive to late_payment_count" in warnings
    ):
        return "proxy_sensitive"
    return "not_proxy_sensitive"


def _recommendation(record: dict[str, Any]) -> tuple[str, str]:
    score = record.get("score_result") or {}
    decision_support = score.get("decision_support") or {}
    code = str(decision_support.get("recommendation_code") or "not_recorded")
    title = str(decision_support.get("title") or "Not recorded")
    return code, title


class MicroScoreRepository:
    """Small SQLite repository for users, sessions, applications, and audits."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.storage_backend = configured_storage_backend()
        if self.storage_backend not in SUPPORTED_STORAGE_BACKENDS:
            raise UnsupportedStorageBackendError(
                "MICROSCORE_STORAGE_BACKEND="
                f"{self.storage_backend!r} is not implemented yet. "
                "Use 'sqlite' for the current prototype; PostgreSQL is tracked "
                "by the readiness metadata but requires a future repository implementation."
            )
        self.db_path = Path(db_path) if db_path is not None else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mfi_organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    region TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    organization_id TEXT REFERENCES mfi_organizations(id),
                    created_at TEXT NOT NULL,
                    disabled_at TEXT,
                    disabled_by TEXT REFERENCES users(email),
                    mfa_attested_at TEXT,
                    mfa_attested_by TEXT REFERENCES users(email),
                    mfa_method TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS staff_invites (
                    token TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    organization_id TEXT NOT NULL REFERENCES mfi_organizations(id),
                    created_by TEXT REFERENCES users(email),
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    accepted_at TEXT,
                    accepted_by TEXT REFERENCES users(email),
                    revoked_at TEXT,
                    revoked_by TEXT REFERENCES users(email),
                    delivered_at TEXT,
                    delivered_by TEXT REFERENCES users(email),
                    delivery_channel TEXT,
                    delivery_recipient TEXT,
                    delivery_url_base TEXT,
                    delivery_note TEXT
                );

                CREATE TABLE IF NOT EXISTS staff_invite_delivery_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    invite_token TEXT NOT NULL REFERENCES staff_invites(token) ON DELETE CASCADE,
                    attempted_at TEXT NOT NULL,
                    attempted_by TEXT REFERENCES users(email),
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    recipient TEXT,
                    delivery_url_base TEXT,
                    note TEXT,
                    error TEXT,
                    worker_status TEXT NOT NULL DEFAULT 'completed',
                    worker_attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_worker_run_at TEXT,
                    dead_letter_at TEXT,
                    last_worker_error TEXT
                );

                CREATE TABLE IF NOT EXISTS staff_invite_delivery_events (
                    event_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL REFERENCES staff_invite_delivery_attempts(attempt_id)
                        ON DELETE CASCADE,
                    invite_token TEXT NOT NULL REFERENCES staff_invites(token) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    mapped_attempt_status TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    occurred_at TEXT,
                    recipient TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(provider, provider_event_id)
                );

                CREATE TABLE IF NOT EXISTS loan_applications (
                    id TEXT PRIMARY KEY,
                    borrower_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    requested_amount REAL NOT NULL,
                    purpose TEXT NOT NULL,
                    district TEXT,
                    settlement_type TEXT,
                    organization_id TEXT REFERENCES mfi_organizations(id),
                    behavioral_signals_json TEXT NOT NULL,
                    score_result_json TEXT,
                    created_at TEXT NOT NULL,
                    scored_at TEXT
                );

                CREATE TABLE IF NOT EXISTS application_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL
                        REFERENCES loan_applications(id) ON DELETE CASCADE,
                    actor_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                    decision TEXT NOT NULL,
                    policy_name TEXT,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_email TEXT,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_versions (
                    version TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    lifecycle_status TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    feature_schema_version TEXT NOT NULL,
                    training_data_label TEXT NOT NULL,
                    random_state INTEGER NOT NULL,
                    metrics_json TEXT NOT NULL,
                    limitations_json TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS portfolio_simulations (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT REFERENCES mfi_organizations(id),
                    actor_email TEXT NOT NULL REFERENCES users(email),
                    portfolio_fingerprint TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_applications_borrower
                    ON loan_applications(borrower_email);
                CREATE INDEX IF NOT EXISTS idx_application_decisions_application
                    ON application_decisions(application_id);
                CREATE INDEX IF NOT EXISTS idx_audit_entity
                    ON audit_events(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_staff_invites_email
                    ON staff_invites(email, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_staff_invite_delivery_attempts_invite
                    ON staff_invite_delivery_attempts(invite_token, attempted_at DESC);
                CREATE INDEX IF NOT EXISTS idx_staff_invite_delivery_events_attempt
                    ON staff_invite_delivery_events(attempt_id, received_at DESC);
                CREATE INDEX IF NOT EXISTS idx_staff_invite_delivery_events_invite
                    ON staff_invite_delivery_events(invite_token, received_at DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_single_active
                    ON model_versions(is_active)
                    WHERE is_active = 1;
                CREATE INDEX IF NOT EXISTS idx_portfolio_simulations_organization
                    ON portfolio_simulations(organization_id, created_at DESC);
                """
            )
            _ensure_column(
                connection,
                "users",
                "organization_id",
                "TEXT REFERENCES mfi_organizations(id)",
            )
            _ensure_column(connection, "users", "disabled_at", "TEXT")
            _ensure_column(
                connection,
                "users",
                "disabled_by",
                "TEXT REFERENCES users(email)",
            )
            _ensure_column(connection, "users", "mfa_attested_at", "TEXT")
            _ensure_column(
                connection,
                "users",
                "mfa_attested_by",
                "TEXT REFERENCES users(email)",
            )
            _ensure_column(connection, "users", "mfa_method", "TEXT")
            _ensure_column(
                connection,
                "loan_applications",
                "organization_id",
                "TEXT REFERENCES mfi_organizations(id)",
            )
            _ensure_column(connection, "staff_invites", "revoked_at", "TEXT")
            _ensure_column(
                connection,
                "staff_invites",
                "revoked_by",
                "TEXT REFERENCES users(email)",
            )
            _ensure_column(connection, "staff_invites", "delivered_at", "TEXT")
            _ensure_column(
                connection,
                "staff_invites",
                "delivered_by",
                "TEXT REFERENCES users(email)",
            )
            _ensure_column(connection, "staff_invites", "delivery_channel", "TEXT")
            _ensure_column(connection, "staff_invites", "delivery_recipient", "TEXT")
            _ensure_column(connection, "staff_invites", "delivery_url_base", "TEXT")
            _ensure_column(connection, "staff_invites", "delivery_note", "TEXT")
            _ensure_column(
                connection,
                "staff_invite_delivery_attempts",
                "worker_status",
                "TEXT NOT NULL DEFAULT 'completed'",
            )
            _ensure_column(
                connection,
                "staff_invite_delivery_attempts",
                "worker_attempt_count",
                "INTEGER NOT NULL DEFAULT 0",
            )
            _ensure_column(
                connection,
                "staff_invite_delivery_attempts",
                "next_worker_run_at",
                "TEXT",
            )
            _ensure_column(
                connection,
                "staff_invite_delivery_attempts",
                "dead_letter_at",
                "TEXT",
            )
            _ensure_column(
                connection,
                "staff_invite_delivery_attempts",
                "last_worker_error",
                "TEXT",
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_applications_organization
                ON loan_applications(organization_id)
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO model_versions (
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
                VALUES (?, ?, ?, 'active', 1, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    DEFAULT_MODEL_VERSION,
                    DEFAULT_MODEL_NAME,
                    "logistic_regression",
                    DEFAULT_FEATURE_SCHEMA_VERSION,
                    DEFAULT_TRAINING_DATA_LABEL,
                    DEFAULT_MODEL_RANDOM_STATE,
                    _json_dumps({"validation_status": "research_only"}),
                    _json_dumps(
                        [
                            "Trained on synthetic data; not validated for real lending.",
                            "Late-payment history is proxy-sensitive and requires human review.",
                        ]
                    ),
                    _now_iso(),
                    _now_iso(),
                ),
            )
            active_count = connection.execute(
                "SELECT COUNT(*) AS count FROM model_versions WHERE is_active = 1"
            ).fetchone()["count"]
            if active_count == 0:
                connection.execute(
                    """
                    UPDATE model_versions
                    SET lifecycle_status = 'active', is_active = 1, activated_at = ?
                    WHERE version = ?
                    """,
                    (_now_iso(), DEFAULT_MODEL_VERSION),
                )

    def storage_readiness(self) -> dict[str, Any]:
        """Return deterministic storage metadata for migration planning."""

        return {
            "backend": self.storage_backend,
            "status": "ready",
            "production_ready": False,
            "database_path": str(self.db_path),
            "database_exists": self.db_path.exists(),
            "required_tables": list(REQUIRED_SCHEMA_TABLES),
            "json_columns": list(JSON_TEXT_COLUMNS),
            "tenant_scoped_tables": list(TENANT_SCOPED_TABLES),
            "capabilities": [
                {
                    "id": "sqlite_idempotent_startup_migrations",
                    "status": "ready",
                    "detail": (
                        "Repository startup creates missing tables and adds legacy columns "
                        "without deleting local development data."
                    ),
                },
                {
                    "id": "sqlite_foreign_keys_per_connection",
                    "status": "ready",
                    "detail": "Every SQLite connection enables PRAGMA foreign_keys = ON.",
                },
                {
                    "id": "deterministic_json_text_serialization",
                    "status": "ready",
                    "detail": "Structured values are serialized with sorted ASCII JSON text.",
                },
                {
                    "id": "organization_scoped_repository_queries",
                    "status": "ready",
                    "detail": (
                        "Application queues, analytics, simulations, staff invites, and "
                        "review access keep organization_id as the tenant boundary."
                    ),
                },
                {
                    "id": "postgresql_repository_backend",
                    "status": "planned",
                    "detail": (
                        "PostgreSQL is not an active backend in this prototype and needs "
                        "schema migrations plus integration tests before use."
                    ),
                },
            ],
            "postgresql_migration_status": "planned",
            "postgresql_migration_checklist": list(POSTGRESQL_MIGRATION_CHECKLIST),
            "limitation": (
                "PostgreSQL Readiness v1 documents the storage contract and startup "
                "validation while the runtime repository remains SQLite-only."
            ),
        }

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
        try:
            with self._connection() as connection:
                connection.execute(
                    """
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
                    VALUES (?, ?, 'logistic_regression', 'candidate', 0, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        version,
                        model_name,
                        feature_schema_version,
                        training_data_label,
                        random_state,
                        _json_dumps(metrics),
                        _json_dumps(limitations),
                        created_by,
                        _now_iso(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateModelVersionError(version) from exc
        return self.get_model_version(version) or {}

    def get_model_version(self, version: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM model_versions WHERE version = ?",
                (version,),
            ).fetchone()
        return self._model_version_from_row(row) if row else None

    def get_active_model_version(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM model_versions
                WHERE is_active = 1
                ORDER BY activated_at DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return self._model_version_from_row(row) if row else None

    def list_model_versions(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM model_versions
                ORDER BY is_active DESC, created_at DESC, version DESC
                """
            ).fetchall()
        return [self._model_version_from_row(row) for row in rows]

    def activate_model_version(self, version: str) -> dict[str, Any] | None:
        activated_at = _now_iso()
        with self._connection() as connection:
            target = connection.execute(
                "SELECT version FROM model_versions WHERE version = ?",
                (version,),
            ).fetchone()
            if target is None:
                return None
            connection.execute(
                """
                UPDATE model_versions
                SET lifecycle_status = 'inactive', is_active = 0
                WHERE is_active = 1 AND version <> ?
                """,
                (version,),
            )
            connection.execute(
                """
                UPDATE model_versions
                SET lifecycle_status = 'active', is_active = 1, activated_at = ?
                WHERE version = ?
                """,
                (activated_at, version),
            )
        return self.get_model_version(version)

    def create_portfolio_simulation(
        self,
        *,
        simulation_id: str,
        organization_id: str | None,
        actor_email: str,
        portfolio_fingerprint: str,
        request_payload: dict[str, Any],
        result_payload: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO portfolio_simulations (
                    id,
                    organization_id,
                    actor_email,
                    portfolio_fingerprint,
                    request_json,
                    result_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    simulation_id,
                    organization_id,
                    actor_email,
                    portfolio_fingerprint,
                    _json_dumps(request_payload),
                    _json_dumps(result_payload),
                    created_at,
                ),
            )
        return self.get_portfolio_simulation(simulation_id) or {}

    def get_portfolio_simulation(self, simulation_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM portfolio_simulations WHERE id = ?",
                (simulation_id,),
            ).fetchone()
        return self._portfolio_simulation_from_row(row) if row else None

    def list_portfolio_simulations(
        self,
        organization_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if organization_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM portfolio_simulations
                    ORDER BY created_at DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM portfolio_simulations
                    WHERE organization_id = ?
                    ORDER BY created_at DESC
                    """,
                    (organization_id,),
                ).fetchall()
        return [self._portfolio_simulation_from_row(row) for row in rows]

    def create_organization(
        self,
        *,
        organization_id: str,
        name: str,
        region: str,
    ) -> dict[str, Any]:
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO mfi_organizations (id, name, region, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (organization_id, name, region, _now_iso()),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateOrganizationError(organization_id) from exc
        return self.get_organization(organization_id) or {}

    def get_organization(self, organization_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, name, region, created_at
                FROM mfi_organizations
                WHERE id = ?
                """,
                (organization_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_organizations(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, name, region, created_at
                FROM mfi_organizations
                ORDER BY name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        email,
                        password_hash,
                        role,
                        organization_id,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (email, password_hash, role, organization_id, now),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError(email) from exc

        self.record_audit_event(
            actor_email=email,
            action="user_registered",
            entity_type="user",
            entity_id=email,
            details={"role": role, "organization_id": organization_id},
        )
        return self.get_user(email) or {}

    def get_user(self, email: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
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
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
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
            ).fetchall()
        return [dict(row) for row in rows]

    def disable_user(self, email: str, disabled_by: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT email, disabled_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
            if existing is None:
                return None
            if existing["disabled_at"] is None:
                connection.execute(
                    """
                    UPDATE users
                    SET disabled_at = ?, disabled_by = ?
                    WHERE email = ? AND disabled_at IS NULL
                    """,
                    (now, disabled_by, email),
                )
            revoked_sessions = connection.execute(
                "DELETE FROM sessions WHERE email = ?",
                (email,),
            ).rowcount
        disabled = self.get_user(email) or {}
        disabled["revoked_session_count"] = revoked_sessions
        disabled["was_already_disabled"] = existing["disabled_at"] is not None
        return disabled

    def reactivate_user(self, email: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT email, disabled_at, disabled_by
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
            if existing is None:
                return None
            if existing["disabled_at"] is not None:
                connection.execute(
                    """
                    UPDATE users
                    SET disabled_at = NULL, disabled_by = NULL
                    WHERE email = ? AND disabled_at IS NOT NULL
                    """,
                    (email,),
                )
        reactivated = self.get_user(email) or {}
        reactivated["was_already_active"] = existing["disabled_at"] is None
        reactivated["previous_disabled_at"] = existing["disabled_at"]
        reactivated["previous_disabled_by"] = existing["disabled_by"]
        return reactivated

    def attest_user_mfa(
        self,
        email: str,
        attested_by: str,
        method: str,
    ) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT email, mfa_attested_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
            if existing is None:
                return None
            if existing["mfa_attested_at"] is None:
                connection.execute(
                    """
                    UPDATE users
                    SET mfa_attested_at = ?, mfa_attested_by = ?, mfa_method = ?
                    WHERE email = ? AND mfa_attested_at IS NULL
                    """,
                    (now, attested_by, method, email),
                )
        attested = self.get_user(email) or {}
        attested["was_already_attested"] = existing["mfa_attested_at"] is not None
        return attested

    def create_staff_invite(
        self,
        *,
        token: str,
        email: str,
        role: str,
        organization_id: str,
        created_by: str,
        expires_at: str,
    ) -> dict[str, Any]:
        now = _now_iso()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO staff_invites (
                    token,
                    email,
                    role,
                    organization_id,
                    created_by,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (token, email, role, organization_id, created_by, now, expires_at),
            )
        return self.get_staff_invite(token) or {}

    def get_staff_invite(self, token: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    token,
                    email,
                    role,
                    organization_id,
                    created_by,
                    created_at,
                    expires_at,
                    accepted_at,
                    accepted_by,
                    revoked_at,
                    revoked_by,
                    delivered_at,
                    delivered_by,
                    delivery_channel,
                    delivery_recipient,
                    delivery_url_base,
                    delivery_note,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                    ), 0) AS delivery_attempt_count,
                    (
                        SELECT attempted_at
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                        ORDER BY attempted_at DESC, attempt_id DESC
                        LIMIT 1
                    ) AS last_delivery_attempt_at,
                    (
                        SELECT status
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                        ORDER BY attempted_at DESC, attempt_id DESC
                        LIMIT 1
                    ) AS last_delivery_status,
                    (
                        SELECT provider
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                        ORDER BY attempted_at DESC, attempt_id DESC
                        LIMIT 1
                    ) AS last_delivery_provider,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM staff_invite_delivery_events
                        WHERE invite_token = staff_invites.token
                    ), 0) AS delivery_event_count,
                    (
                        SELECT received_at
                        FROM staff_invite_delivery_events
                        WHERE invite_token = staff_invites.token
                        ORDER BY received_at DESC, event_id DESC
                        LIMIT 1
                    ) AS last_delivery_event_at,
                    (
                        SELECT event_type
                        FROM staff_invite_delivery_events
                        WHERE invite_token = staff_invites.token
                        ORDER BY received_at DESC, event_id DESC
                        LIMIT 1
                    ) AS last_delivery_event_type
                FROM staff_invites
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
        return dict(row) if row else None

    def list_staff_invites(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    token,
                    email,
                    role,
                    organization_id,
                    created_by,
                    created_at,
                    expires_at,
                    accepted_at,
                    accepted_by,
                    revoked_at,
                    revoked_by,
                    delivered_at,
                    delivered_by,
                    delivery_channel,
                    delivery_recipient,
                    delivery_url_base,
                    delivery_note,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                    ), 0) AS delivery_attempt_count,
                    (
                        SELECT attempted_at
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                        ORDER BY attempted_at DESC, attempt_id DESC
                        LIMIT 1
                    ) AS last_delivery_attempt_at,
                    (
                        SELECT status
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                        ORDER BY attempted_at DESC, attempt_id DESC
                        LIMIT 1
                    ) AS last_delivery_status,
                    (
                        SELECT provider
                        FROM staff_invite_delivery_attempts
                        WHERE invite_token = staff_invites.token
                        ORDER BY attempted_at DESC, attempt_id DESC
                        LIMIT 1
                    ) AS last_delivery_provider,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM staff_invite_delivery_events
                        WHERE invite_token = staff_invites.token
                    ), 0) AS delivery_event_count,
                    (
                        SELECT received_at
                        FROM staff_invite_delivery_events
                        WHERE invite_token = staff_invites.token
                        ORDER BY received_at DESC, event_id DESC
                        LIMIT 1
                    ) AS last_delivery_event_at,
                    (
                        SELECT event_type
                        FROM staff_invite_delivery_events
                        WHERE invite_token = staff_invites.token
                        ORDER BY received_at DESC, event_id DESC
                        LIMIT 1
                    ) AS last_delivery_event_type
                FROM staff_invites
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_staff_invite_accepted(self, token: str, accepted_by: str) -> bool:
        now = _now_iso()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE staff_invites
                SET accepted_at = ?, accepted_by = ?
                WHERE token = ? AND accepted_at IS NULL AND revoked_at IS NULL
                """,
                (now, accepted_by, token),
            )
        return cursor.rowcount > 0

    def mark_staff_invite_revoked(self, token: str, revoked_by: str) -> bool:
        now = _now_iso()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE staff_invites
                SET revoked_at = ?, revoked_by = ?
                WHERE token = ? AND accepted_at IS NULL AND revoked_at IS NULL
                """,
                (now, revoked_by, token),
            )
        return cursor.rowcount > 0

    def mark_staff_invite_delivered(
        self,
        token: str,
        *,
        delivered_by: str | None,
        channel: str,
        recipient: str | None,
        url_base: str,
        note: str | None,
    ) -> dict[str, Any] | None:
        now = _now_iso()
        existing = self.get_staff_invite(token)
        if existing is None:
            return None
        was_already_delivered = existing.get("delivered_at") is not None
        if not was_already_delivered:
            with self._connection() as connection:
                connection.execute(
                    """
                    UPDATE staff_invites
                    SET
                        delivered_at = ?,
                        delivered_by = ?,
                        delivery_channel = ?,
                        delivery_recipient = ?,
                        delivery_url_base = ?,
                        delivery_note = ?
                    WHERE token = ? AND delivered_at IS NULL
                    """,
                    (now, delivered_by, channel, recipient, url_base, note, token),
                )
        delivered = self.get_staff_invite(token) or existing
        delivered["was_already_delivered"] = was_already_delivered
        return delivered

    def record_staff_invite_delivery_attempt(
        self,
        *,
        attempt_id: str,
        token: str,
        attempted_by: str,
        provider: str,
        status: str,
        channel: str,
        recipient: str | None,
        url_base: str | None,
        note: str | None,
        error: str | None = None,
    ) -> dict[str, Any]:
        attempted_at = _now_iso()
        worker_state = _initial_delivery_worker_state(status, attempted_at)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO staff_invite_delivery_attempts (
                    attempt_id,
                    invite_token,
                    attempted_at,
                    attempted_by,
                    provider,
                    status,
                    channel,
                    recipient,
                    delivery_url_base,
                    note,
                    error,
                    worker_status,
                    worker_attempt_count,
                    next_worker_run_at,
                    dead_letter_at,
                    last_worker_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    token,
                    attempted_at,
                    attempted_by,
                    provider,
                    status,
                    channel,
                    recipient,
                    url_base,
                    note,
                    error,
                    worker_state["worker_status"],
                    worker_state["worker_attempt_count"],
                    worker_state["next_worker_run_at"],
                    worker_state["dead_letter_at"],
                    worker_state["last_worker_error"],
                ),
            )
        return self.get_staff_invite_delivery_attempt(attempt_id) or {}

    def get_staff_invite_delivery_attempt(
        self,
        attempt_id: str,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    attempt_id,
                    invite_token,
                    attempted_at,
                    attempted_by,
                    provider,
                    status,
                    channel,
                    recipient,
                    delivery_url_base,
                    note,
                    error,
                    worker_status,
                    worker_attempt_count,
                    next_worker_run_at,
                    dead_letter_at,
                    last_worker_error
                FROM staff_invite_delivery_attempts
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_staff_invite_delivery_attempts(
        self,
        token: str,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    attempt_id,
                    invite_token,
                    attempted_at,
                    attempted_by,
                    provider,
                    status,
                    channel,
                    recipient,
                    delivery_url_base,
                    note,
                    error,
                    worker_status,
                    worker_attempt_count,
                    next_worker_run_at,
                    dead_letter_at,
                    last_worker_error
                FROM staff_invite_delivery_attempts
                WHERE invite_token = ?
                ORDER BY attempted_at DESC, attempt_id DESC
                """,
                (token,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_staff_invite_delivery_attempt_status(
        self,
        attempt_id: str,
        *,
        status: str,
        error: str | None,
        worker_status: str | None = None,
        next_worker_run_at: str | None = None,
        dead_letter_at: str | None = None,
        last_worker_error: str | None = None,
    ) -> dict[str, Any] | None:
        worker_status_value = worker_status
        if worker_status_value is None:
            worker_status_value = "retry_scheduled" if status == "queued" else "completed"
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE staff_invite_delivery_attempts
                SET
                    status = ?,
                    error = ?,
                    worker_status = ?,
                    next_worker_run_at = ?,
                    dead_letter_at = ?,
                    last_worker_error = ?
                WHERE attempt_id = ?
                """,
                (
                    status,
                    error,
                    worker_status_value,
                    next_worker_run_at,
                    dead_letter_at,
                    last_worker_error,
                    attempt_id,
                ),
            )
        if cursor.rowcount == 0:
            return None
        return self.get_staff_invite_delivery_attempt(attempt_id)

    def update_staff_invite_delivery_worker_state(
        self,
        attempt_id: str,
        *,
        status: str,
        error: str | None,
        worker_status: str,
        worker_attempt_count: int,
        next_worker_run_at: str | None,
        dead_letter_at: str | None,
        last_worker_error: str | None,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE staff_invite_delivery_attempts
                SET
                    status = ?,
                    error = ?,
                    worker_status = ?,
                    worker_attempt_count = ?,
                    next_worker_run_at = ?,
                    dead_letter_at = ?,
                    last_worker_error = ?
                WHERE attempt_id = ?
                """,
                (
                    status,
                    error,
                    worker_status,
                    worker_attempt_count,
                    next_worker_run_at,
                    dead_letter_at,
                    last_worker_error,
                    attempt_id,
                ),
            )
        if cursor.rowcount == 0:
            return None
        return self.get_staff_invite_delivery_attempt(attempt_id)

    def list_staff_invite_delivery_outbox_attempts(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    attempts.attempt_id,
                    attempts.invite_token,
                    attempts.attempted_at,
                    attempts.attempted_by,
                    attempts.provider,
                    attempts.status,
                    attempts.channel,
                    attempts.recipient,
                    attempts.delivery_url_base,
                    attempts.note,
                    attempts.error,
                    attempts.worker_status,
                    attempts.worker_attempt_count,
                    attempts.next_worker_run_at,
                    attempts.dead_letter_at,
                    attempts.last_worker_error,
                    invites.email,
                    invites.role,
                    invites.organization_id,
                    invites.expires_at,
                    invites.accepted_at,
                    invites.revoked_at,
                    invites.delivered_at,
                    (
                        SELECT events.event_type
                        FROM staff_invite_delivery_events AS events
                        WHERE events.attempt_id = attempts.attempt_id
                        ORDER BY events.received_at DESC, events.event_id DESC
                        LIMIT 1
                    ) AS last_delivery_event_type
                FROM staff_invite_delivery_attempts AS attempts
                JOIN staff_invites AS invites
                    ON invites.token = attempts.invite_token
                ORDER BY
                    CASE
                        WHEN attempts.next_worker_run_at IS NULL THEN 1
                        ELSE 0
                    END,
                    attempts.next_worker_run_at ASC,
                    attempts.attempted_at DESC,
                    attempts.attempt_id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_staff_invite_delivery_event(
        self,
        *,
        event_id: str,
        provider: str,
        provider_event_id: str,
        attempt_id: str,
        token: str,
        event_type: str,
        mapped_attempt_status: str,
        occurred_at: str | None,
        recipient: str | None,
        error: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        received_at = _now_iso()
        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT event_id
                FROM staff_invite_delivery_events
                WHERE provider = ? AND provider_event_id = ?
                """,
                (provider, provider_event_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO staff_invite_delivery_events (
                        event_id,
                        provider,
                        provider_event_id,
                        attempt_id,
                        invite_token,
                        event_type,
                        mapped_attempt_status,
                        received_at,
                        occurred_at,
                        recipient,
                        error,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        provider,
                        provider_event_id,
                        attempt_id,
                        token,
                        event_type,
                        mapped_attempt_status,
                        received_at,
                        occurred_at,
                        recipient,
                        error,
                        _json_dumps(metadata),
                    ),
                )
                stored_event_id = event_id
                was_duplicate = False
            else:
                stored_event_id = existing["event_id"]
                was_duplicate = True
        event = self.get_staff_invite_delivery_event(stored_event_id) or {}
        event["was_duplicate"] = was_duplicate
        return event

    def get_staff_invite_delivery_event(
        self,
        event_id: str,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    event_id,
                    provider,
                    provider_event_id,
                    attempt_id,
                    invite_token,
                    event_type,
                    mapped_attempt_status,
                    received_at,
                    occurred_at,
                    recipient,
                    error,
                    metadata_json
                FROM staff_invite_delivery_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        event = dict(row)
        event["metadata"] = _json_loads(event.pop("metadata_json")) or {}
        return event

    def list_staff_invite_delivery_events(
        self,
        token: str,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    event_id,
                    provider,
                    provider_event_id,
                    attempt_id,
                    invite_token,
                    event_type,
                    mapped_attempt_status,
                    received_at,
                    occurred_at,
                    recipient,
                    error,
                    metadata_json
                FROM staff_invite_delivery_events
                WHERE invite_token = ?
                ORDER BY received_at DESC, event_id DESC
                """,
                (token,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            event["metadata"] = _json_loads(event.pop("metadata_json")) or {}
            event["was_duplicate"] = False
            events.append(event)
        return events

    def assign_user_organization(self, email: str, organization_id: str | None) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE users SET organization_id = ? WHERE email = ?",
                (organization_id, email),
            )

    def create_session(
        self,
        token: str,
        email: str,
        *,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        stored_created_at = created_at or _now_iso()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, email, created_at)
                VALUES (?, ?, ?)
                """,
                (token, email, stored_created_at),
            )
        return session_expiry_metadata(stored_created_at)

    def get_user_by_token(
        self,
        token: str,
        *,
        now: datetime | None = None,
        ttl_hours: float | None = None,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
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
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
        if row is None:
            return None
        if row["disabled_at"] is not None:
            self.revoke_session(token)
            return None

        metadata = session_expiry_metadata(row["session_created_at"], ttl_hours=ttl_hours)
        expires_at = _parse_utc_datetime(metadata["session_expires_at"])
        if expires_at <= (now or datetime.now(timezone.utc)):
            self.revoke_session(token)
            return None

        user = dict(row)
        user.update(metadata)
        return user

    def revoke_session(self, token: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return cursor.rowcount > 0

    def list_active_sessions(
        self,
        *,
        staff_only: bool = False,
        now: datetime | None = None,
        ttl_hours: float | None = None,
    ) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        with self._connection() as connection:
            rows = connection.execute(
                """
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
            ).fetchall()

        active_sessions: list[dict[str, Any]] = []
        expired_or_disabled_tokens: list[str] = []
        for row in rows:
            if row["disabled_at"] is not None:
                expired_or_disabled_tokens.append(row["token"])
                continue
            if staff_only and row["role"] not in {"admin", "mfi_analyst"}:
                continue
            metadata = session_expiry_metadata(row["session_created_at"], ttl_hours=ttl_hours)
            expires_at = _parse_utc_datetime(metadata["session_expires_at"])
            if expires_at <= now:
                expired_or_disabled_tokens.append(row["token"])
                continue
            session = dict(row)
            session.update(metadata)
            session["session_id"] = hashlib.sha256(row["token"].encode("utf-8")).hexdigest()
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
            if self.revoke_session(session["token"]):
                return session
            return None
        return None

    def create_application(
        self,
        *,
        application_id: str,
        borrower_email: str,
        requested_amount: float,
        purpose: str,
        district: str | None,
        settlement_type: str | None,
        behavioral_signals: dict[str, Any],
        consent_version: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    borrower_email,
                    "submitted",
                    requested_amount,
                    purpose,
                    district,
                    settlement_type,
                    organization_id,
                    _json_dumps(behavioral_signals),
                    None,
                    _now_iso(),
                    None,
                ),
            )

        self.record_audit_event(
            actor_email=borrower_email,
            action="application_created",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "requested_amount": requested_amount,
                "consent_confirmed": consent_version is not None,
                "consent_version": consent_version,
                "organization_id": organization_id,
            },
        )
        return self.get_application(application_id) or {}

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM loan_applications
                WHERE id = ?
                """,
                (application_id,),
            ).fetchone()
        return self._application_from_row(row) if row else None

    def list_applications(
        self,
        organization_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if organization_id is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM loan_applications
                    ORDER BY created_at DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM loan_applications
                    WHERE organization_id = ?
                    ORDER BY created_at DESC
                    """,
                    (organization_id,),
                ).fetchall()
        return [self._application_from_row(row) for row in rows]

    def list_borrower_applications(self, borrower_email: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM loan_applications
                WHERE borrower_email = ?
                ORDER BY created_at DESC
                """,
                (borrower_email,),
            ).fetchall()
        return [self._application_from_row(row) for row in rows]

    def assign_application_organization(
        self,
        application_id: str,
        organization_id: str,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE loan_applications SET organization_id = ? WHERE id = ?",
                (organization_id, application_id),
            )

    def clear_applications(self, *, actor_email: str) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM loan_applications").fetchone()
            deleted_count = int(row["count"])
            connection.execute("DELETE FROM loan_applications")

        self.record_audit_event(
            actor_email=actor_email,
            action="applications_cleared",
            entity_type="loan_application",
            entity_id=None,
            details={"deleted_count": deleted_count},
        )
        return deleted_count

    def update_application_score(
        self,
        *,
        application_id: str,
        score_result: dict[str, Any],
        actor_email: str,
    ) -> dict[str, Any] | None:
        scored_at = _now_iso()
        with self._connection() as connection:
            current = connection.execute(
                "SELECT status, score_result_json FROM loan_applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            if current is None:
                return None
            previous_status = str(current["status"])
            if previous_status in TERMINAL_APPLICATION_STATUSES:
                raise InvalidApplicationTransitionError(
                    f"Cannot score an application after it is {previous_status}"
                )
            next_status = "scored" if previous_status == "submitted" else previous_status
            action = "application_scored" if current["score_result_json"] is None else "application_rescored"
            connection.execute(
                """
                UPDATE loan_applications
                SET status = ?, score_result_json = ?, scored_at = ?
                WHERE id = ?
                """,
                (next_status, _json_dumps(score_result), scored_at, application_id),
            )

        self.record_audit_event(
            actor_email=actor_email,
            action=action,
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "model_version": score_result.get("model_version"),
                "risk_band": score_result.get("risk_band"),
                "previous_status": previous_status,
                "status": next_status,
            },
        )
        return self.get_application(application_id)

    def record_application_decision(
        self,
        *,
        application_id: str,
        actor_email: str,
        decision: str,
        policy_name: str | None,
        note: str,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            current = connection.execute(
                "SELECT status, score_result_json FROM loan_applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            if current is None:
                return None
            previous_status = str(current["status"])
            if current["score_result_json"] is None:
                raise InvalidApplicationTransitionError(
                    "Score the application before recording an MFI decision"
                )
            if decision not in DECISION_TRANSITIONS.get(previous_status, set()):
                raise InvalidApplicationTransitionError(
                    f"Cannot record {decision} while application status is {previous_status}"
                )
            next_status = DECISION_WORKFLOW_STATUSES[decision]
            connection.execute(
                """
                INSERT INTO application_decisions (
                    application_id,
                    actor_email,
                    decision,
                    policy_name,
                    note,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    actor_email,
                    decision,
                    policy_name,
                    note,
                    _now_iso(),
                ),
            )
            connection.execute(
                "UPDATE loan_applications SET status = ? WHERE id = ?",
                (next_status, application_id),
            )

        self.record_audit_event(
            actor_email=actor_email,
            action="application_decision_recorded",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "decision": decision,
                "policy_name": policy_name,
                "previous_status": previous_status,
                "status": next_status,
            },
        )
        return self.get_application(application_id)

    def segment_analytics(
        self,
        organization_id: str | None = None,
    ) -> list[dict[str, Any]]:
        scored = [
            item
            for item in self.list_applications(organization_id)
            if item.get("score_result")
        ]
        segments: dict[tuple[str, str], list[float]] = {}

        for item in scored:
            signals = item["behavioral_signals"]
            segment_values = {
                "settlement_type": item.get("settlement_type") or signals.get("settlement_type") or "unknown",
                "pavlodar_district": item.get("district") or signals.get("pavlodar_district") or "unknown",
                "gender": signals.get("gender") or "unknown",
                "employment_status": signals.get("employment_status") or "unknown",
            }
            probability = item["score_result"]["high_risk_probability"]
            for feature, value in segment_values.items():
                segments.setdefault((feature, str(value)), []).append(probability)

        rows: list[dict[str, Any]] = []
        for (feature, value), probabilities in sorted(segments.items()):
            rows.append(
                {
                    "segment_feature": feature,
                    "segment_value": value,
                    "n": len(probabilities),
                    "avg_high_risk_probability": sum(probabilities) / len(probabilities),
                    "high_risk_share": sum(probability >= 0.65 for probability in probabilities)
                    / len(probabilities),
                }
            )
        return rows

    def decision_analytics(
        self,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        applications = self.list_applications(organization_id)
        decision_records = [
            application for application in applications if application.get("decision_result")
        ]
        decisions = [application["decision_result"] for application in decision_records]
        total_decisions = len(decisions)

        decision_rows: list[dict[str, Any]] = []
        for decision in DECISION_VALUES:
            count = sum(item["decision"] == decision for item in decisions)
            decision_rows.append(
                {
                    "decision": decision,
                    "count": count,
                    "rate": _safe_rate(count, total_decisions),
                }
            )

        policy_counts: dict[tuple[str, str], int] = {}
        for item in decisions:
            key = (item["policy_name"] or "not_recorded", item["decision"])
            policy_counts[key] = policy_counts.get(key, 0) + 1

        policy_rows = [
            {
                "policy_name": policy_name,
                "decision": decision,
                "count": count,
                "rate": _safe_rate(count, total_decisions),
            }
            for (policy_name, decision), count in sorted(policy_counts.items())
        ]

        return {
            "application_count": len(applications),
            "decided_application_count": total_decisions,
            "decision_rows": decision_rows,
            "policy_rows": policy_rows,
            "risk_rows": self._decision_risk_rows(decision_records),
            "district_rows": self._decision_district_rows(decision_records),
            "recommendation_rows": self._decision_recommendation_rows(decision_records),
            "proxy_rows": self._decision_proxy_rows(decision_records),
            "note": "Decision analytics summarize the latest human MFI decision per application.",
        }

    def _decision_risk_rows(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            score = record.get("score_result") or {}
            risk_band = score.get("risk_band")
            if risk_band not in {"low", "medium", "high"}:
                continue
            groups.setdefault(str(risk_band), []).append(record)

        rows: list[dict[str, Any]] = []
        for risk_band in ("low", "medium", "high"):
            group = groups.get(risk_band, [])
            for decision in DECISION_VALUES:
                matches = [
                    record
                    for record in group
                    if record["decision_result"]["decision"] == decision
                ]
                if not matches:
                    continue
                rows.append(
                    {
                        "risk_band": risk_band,
                        "decision": decision,
                        "count": len(matches),
                        "rate_within_risk_band": _safe_rate(len(matches), len(group)),
                        "mean_high_risk_probability": _mean(
                            _high_risk_probabilities(matches)
                        ),
                    }
                )
        return rows

    def _decision_district_rows(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            signals = record.get("behavioral_signals") or {}
            district = record.get("district") or signals.get("pavlodar_district") or "unknown"
            groups.setdefault(str(district), []).append(record)

        rows: list[dict[str, Any]] = []
        for district, group in sorted(groups.items()):
            for decision in DECISION_VALUES:
                matches = [
                    record
                    for record in group
                    if record["decision_result"]["decision"] == decision
                ]
                if not matches:
                    continue
                rows.append(
                    {
                        "district": district,
                        "decision": decision,
                        "count": len(matches),
                        "rate_within_district": _safe_rate(len(matches), len(group)),
                        "mean_high_risk_probability": _mean(
                            _high_risk_probabilities(matches)
                        ),
                    }
                )
        return rows

    def _decision_recommendation_rows(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for record in records:
            groups.setdefault(_recommendation(record), []).append(record)

        rows: list[dict[str, Any]] = []
        for (code, title), group in sorted(groups.items()):
            for decision in DECISION_VALUES:
                matches = [
                    record
                    for record in group
                    if record["decision_result"]["decision"] == decision
                ]
                if not matches:
                    continue
                rows.append(
                    {
                        "recommendation_code": code,
                        "recommendation_title": title,
                        "decision": decision,
                        "count": len(matches),
                        "rate_within_recommendation": _safe_rate(
                            len(matches),
                            len(group),
                        ),
                        "mean_high_risk_probability": _mean(
                            _high_risk_probabilities(matches)
                        ),
                    }
                )
        return rows

    def _decision_proxy_rows(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            groups.setdefault(_proxy_sensitivity_bucket(record), []).append(record)

        rows: list[dict[str, Any]] = []
        for bucket, group in sorted(groups.items()):
            for decision in DECISION_VALUES:
                matches = [
                    record
                    for record in group
                    if record["decision_result"]["decision"] == decision
                ]
                if not matches:
                    continue
                rows.append(
                    {
                        "proxy_sensitivity_bucket": bucket,
                        "decision": decision,
                        "count": len(matches),
                        "rate_within_bucket": _safe_rate(len(matches), len(group)),
                        "mean_high_risk_probability": _mean(
                            _high_risk_probabilities(matches)
                        ),
                        "mean_proxy_sensitivity_delta": _mean(
                            _proxy_sensitivity_deltas(matches)
                        ),
                    }
                )
        return rows

    def record_audit_event(
        self,
        *,
        actor_email: str | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, Any],
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    actor_email,
                    action,
                    entity_type,
                    entity_id,
                    details_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_email,
                    action,
                    entity_type,
                    entity_id,
                    _json_dumps(details),
                    _now_iso(),
                ),
            )

    def list_audit_events(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM audit_events
                ORDER BY id DESC
                """
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            event["details"] = _json_loads(event.pop("details_json"))
            events.append(event)
        return events

    def list_application_timeline(self, application_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE entity_type = 'loan_application'
                  AND entity_id = ?
                ORDER BY id ASC
                """,
                (application_id,),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            event["details"] = _json_loads(event.pop("details_json"))
            events.append(event)
        return events

    def list_application_decisions(self, application_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, application_id, actor_email, decision, policy_name, note, created_at
                FROM application_decisions
                WHERE application_id = ?
                ORDER BY id ASC
                """,
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _application_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        application = dict(row)
        application["behavioral_signals"] = _json_loads(
            application.pop("behavioral_signals_json")
        )
        application["score_result"] = _json_loads(application.pop("score_result_json"))
        application["decision_result"] = self._latest_application_decision(
            application["id"]
        )
        return application

    @staticmethod
    def _model_version_from_row(row: sqlite3.Row) -> dict[str, Any]:
        model_version = dict(row)
        model_version["is_active"] = bool(model_version["is_active"])
        model_version["metrics"] = _json_loads(model_version.pop("metrics_json")) or {}
        model_version["limitations"] = (
            _json_loads(model_version.pop("limitations_json")) or []
        )
        return model_version

    @staticmethod
    def _portfolio_simulation_from_row(row: sqlite3.Row) -> dict[str, Any]:
        simulation = dict(row)
        simulation["request"] = _json_loads(simulation.pop("request_json")) or {}
        simulation["result"] = _json_loads(simulation.pop("result_json")) or {}
        return simulation

    def _latest_application_decision(self, application_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, application_id, actor_email, decision, policy_name, note, created_at
                FROM application_decisions
                WHERE application_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (application_id,),
            ).fetchone()
        return dict(row) if row else None
