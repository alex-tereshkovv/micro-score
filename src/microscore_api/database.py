"""SQLite persistence for the MicroScore API prototype."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
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


class DuplicateUserError(ValueError):
    """Raised when an email is already registered."""


class DuplicateOrganizationError(ValueError):
    """Raised when an organization id is already registered."""


class DuplicateModelVersionError(ValueError):
    """Raised when a model version is already registered."""


class InvalidApplicationTransitionError(ValueError):
    """Raised when an application lifecycle transition is not allowed."""


def default_database_path() -> Path:
    configured = os.environ.get("MICROSCORE_API_DB_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_API_DB_PATH


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
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                    created_at TEXT NOT NULL
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
            _ensure_column(
                connection,
                "loan_applications",
                "organization_id",
                "TEXT REFERENCES mfi_organizations(id)",
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
                SELECT email, password_hash, role, organization_id, created_at
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
                SELECT email, role, organization_id, created_at
                FROM users
                ORDER BY role, email
                """
            ).fetchall()
        return [dict(row) for row in rows]

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
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, email, created_at)
                VALUES (?, ?, ?)
                """,
                (token, email, created_at or _now_iso()),
            )

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
                    sessions.created_at AS session_created_at
                FROM sessions
                JOIN users ON users.email = sessions.email
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
        if row is None:
            return None

        session_created_at = _parse_utc_datetime(row["session_created_at"])
        expires_at = session_created_at + timedelta(
            hours=ttl_hours if ttl_hours is not None else configured_session_ttl_hours()
        )
        if expires_at <= (now or datetime.now(timezone.utc)):
            self.revoke_session(token)
            return None

        user = dict(row)
        user.pop("session_created_at", None)
        return user

    def revoke_session(self, token: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return cursor.rowcount > 0

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
