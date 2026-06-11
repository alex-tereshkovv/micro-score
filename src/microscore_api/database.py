"""SQLite persistence for the MicroScore API prototype."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3
from typing import Any

from microscore.paths import PROJECT_ROOT

DEFAULT_API_DB_PATH = PROJECT_ROOT / "data" / "app" / "microscore.sqlite3"


class DuplicateUserError(ValueError):
    """Raised when an email is already registered."""


def default_database_path() -> Path:
    configured = os.environ.get("MICROSCORE_API_DB_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_API_DB_PATH


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _json_loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


DECISION_VALUES = ("approve", "review", "decline")
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
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
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

                CREATE INDEX IF NOT EXISTS idx_applications_borrower
                    ON loan_applications(borrower_email);
                CREATE INDEX IF NOT EXISTS idx_application_decisions_application
                    ON application_decisions(application_id);
                CREATE INDEX IF NOT EXISTS idx_audit_entity
                    ON audit_events(entity_type, entity_id);
                """
            )

    def create_user(self, email: str, password_hash: str, role: str) -> dict[str, Any]:
        now = _now_iso()
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO users (email, password_hash, role, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (email, password_hash, role, now),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError(email) from exc

        self.record_audit_event(
            actor_email=email,
            action="user_registered",
            entity_type="user",
            entity_id=email,
            details={"role": role},
        )
        return self.get_user(email) or {}

    def get_user(self, email: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT email, password_hash, role, created_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
        return dict(row) if row else None

    def create_session(self, token: str, email: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, email, created_at)
                VALUES (?, ?, ?)
                """,
                (token, email, _now_iso()),
            )

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT users.email, users.password_hash, users.role, users.created_at
                FROM sessions
                JOIN users ON users.email = sessions.email
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
        return dict(row) if row else None

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
                    behavioral_signals_json,
                    score_result_json,
                    created_at,
                    scored_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    borrower_email,
                    "submitted",
                    requested_amount,
                    purpose,
                    district,
                    settlement_type,
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
            details={"requested_amount": requested_amount},
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

    def list_applications(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM loan_applications
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._application_from_row(row) for row in rows]

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
            connection.execute(
                """
                UPDATE loan_applications
                SET status = ?, score_result_json = ?, scored_at = ?
                WHERE id = ?
                """,
                ("scored", _json_dumps(score_result), scored_at, application_id),
            )

        self.record_audit_event(
            actor_email=actor_email,
            action="application_scored",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "model_version": score_result.get("model_version"),
                "risk_band": score_result.get("risk_band"),
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
        if self.get_application(application_id) is None:
            return None

        with self._connection() as connection:
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

        self.record_audit_event(
            actor_email=actor_email,
            action="application_decision_recorded",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "decision": decision,
                "policy_name": policy_name,
            },
        )
        return self.get_application(application_id)

    def segment_analytics(self) -> list[dict[str, Any]]:
        scored = [item for item in self.list_applications() if item.get("score_result")]
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

    def decision_analytics(self) -> dict[str, Any]:
        applications = self.list_applications()
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
