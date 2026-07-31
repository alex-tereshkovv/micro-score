from __future__ import annotations

import inspect
import tempfile
import unittest

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import MicroScoreRepository  # noqa: E402
from microscore_api.postgres_repository import (  # noqa: E402
    AUDIT_EVENT_COLUMNS,
    ACTIVE_SESSION_COLUMNS,
    LIST_USER_COLUMNS,
    MODEL_VERSION_COLUMNS,
    ORGANIZATION_COLUMNS,
    POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
    POSTGRESQL_REPOSITORY_ADAPTER_MODULE,
    POSTGRESQL_REPOSITORY_ADAPTER_STATUS,
    SESSION_USER_COLUMNS,
    USER_COLUMNS,
    PostgresRepositoryAdapter,
    PostgresRepositoryAdapterSkeleton,
    REPOSITORY_METHOD_GROUPS,
    audit_method_group_parity_snapshot,
    identity_access_method_group_parity_snapshot,
    model_registry_method_group_parity_snapshot,
    model_registry_read_parity_snapshot,
    organization_method_group_parity_snapshot,
    repository_contract_methods,
    repository_contract_summary,
)


class FakePostgresCursor:
    def __init__(
        self,
        rows: list[tuple[object, ...]],
        rowcount: int | None = None,
    ) -> None:
        self._rows = rows
        self.rowcount = len(rows) if rowcount is None else rowcount

    def fetchone(self) -> tuple[object, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)

    def close(self) -> None:
        return None


class FakePostgresConnection:
    def __init__(
        self,
        rows: list[tuple[object, ...]],
        query_log: list[tuple[str, dict[str, object]]],
        audit_rows: list[tuple[object, ...]] | None = None,
        organization_rows: list[tuple[object, ...]] | None = None,
        user_rows: list[tuple[object, ...]] | None = None,
        session_rows: list[tuple[object, ...]] | None = None,
        user_organization_rows: dict[str, str | None] | None = None,
    ) -> None:
        self.rows = rows
        self.audit_rows = list(audit_rows or [])
        self.organization_rows = list(organization_rows or [])
        self.user_rows = list(user_rows or [])
        self.session_rows = list(session_rows or [])
        self.user_organization_rows = dict(user_organization_rows or {})
        for row in self.user_rows:
            self.user_organization_rows.setdefault(
                str(row[USER_COLUMNS.index("email")]),
                row[USER_COLUMNS.index("organization_id")],
            )
        self.query_log = query_log
        self.closed = False
        self.commits = 0
        self.rollbacks = 0

    @staticmethod
    def _row_version(row: tuple[object, ...]) -> object:
        return row[MODEL_VERSION_COLUMNS.index("version")]

    @staticmethod
    def _row_is_active(row: tuple[object, ...]) -> object:
        return row[MODEL_VERSION_COLUMNS.index("is_active")]

    @staticmethod
    def _ordered_rows(rows: list[tuple[object, ...]]) -> list[tuple[object, ...]]:
        created_at_index = MODEL_VERSION_COLUMNS.index("created_at")
        version_index = MODEL_VERSION_COLUMNS.index("version")
        return sorted(
            rows,
            key=lambda row: (
                1 if FakePostgresConnection._row_is_active(row) is True else 0,
                str(row[created_at_index] or ""),
                str(row[version_index] or ""),
            ),
            reverse=True,
        )

    @staticmethod
    def _replace_column(
        row: tuple[object, ...],
        column: str,
        value: object,
    ) -> tuple[object, ...]:
        values = list(row)
        values[MODEL_VERSION_COLUMNS.index(column)] = value
        return tuple(values)

    @staticmethod
    def _row_user_email(row: tuple[object, ...]) -> object:
        return row[USER_COLUMNS.index("email")]

    @staticmethod
    def _row_user_role(row: tuple[object, ...]) -> object:
        return row[USER_COLUMNS.index("role")]

    @staticmethod
    def _row_session_token(row: tuple[object, ...]) -> object:
        return row[0]

    @staticmethod
    def _row_session_email(row: tuple[object, ...]) -> object:
        return row[1]

    @staticmethod
    def _row_session_created_at(row: tuple[object, ...]) -> object:
        return row[2]

    @staticmethod
    def _replace_user_column(
        row: tuple[object, ...],
        column: str,
        value: object,
    ) -> tuple[object, ...]:
        values = list(row)
        values[USER_COLUMNS.index(column)] = value
        return tuple(values)

    def _insert_user(self, params: dict[str, object]) -> None:
        email = params["email"]
        if any(self._row_user_email(row) == email for row in self.user_rows):
            raise ValueError(f"duplicate user: {email}")
        row = tuple(
            {
                "email": email,
                "password_hash": params["password_hash"],
                "role": params["role"],
                "organization_id": params["organization_id"],
                "created_at": params["created_at"],
                "disabled_at": None,
                "disabled_by": None,
                "mfa_attested_at": None,
                "mfa_attested_by": None,
                "mfa_method": None,
            }[column]
            for column in USER_COLUMNS
        )
        self.user_rows.append(row)
        self.user_organization_rows[str(email)] = params["organization_id"]

    def _user_by_email(self, email: object) -> tuple[object, ...] | None:
        for row in self.user_rows:
            if self._row_user_email(row) == email:
                return row
        return None

    def _list_user_rows(self) -> list[tuple[object, ...]]:
        rows = [
            tuple(row[USER_COLUMNS.index(column)] for column in LIST_USER_COLUMNS)
            for row in self.user_rows
        ]
        role_index = LIST_USER_COLUMNS.index("role")
        email_index = LIST_USER_COLUMNS.index("email")
        return sorted(
            rows,
            key=lambda row: (str(row[role_index]), str(row[email_index])),
        )

    def _update_user_row(
        self,
        email: object,
        replacements: dict[str, object],
        *,
        require_null: str | None = None,
        require_not_null: str | None = None,
    ) -> int:
        updated_rows: list[tuple[object, ...]] = []
        rowcount = 0
        for row in self.user_rows:
            if self._row_user_email(row) != email:
                updated_rows.append(row)
                continue
            if require_null is not None and row[USER_COLUMNS.index(require_null)] is not None:
                updated_rows.append(row)
                continue
            if require_not_null is not None and row[USER_COLUMNS.index(require_not_null)] is None:
                updated_rows.append(row)
                continue
            for column, value in replacements.items():
                row = self._replace_user_column(row, column, value)
            updated_rows.append(row)
            rowcount += 1
        self.user_rows = updated_rows
        if "organization_id" in replacements:
            self.user_organization_rows[str(email)] = replacements["organization_id"]
        return rowcount

    def _insert_session(self, params: dict[str, object]) -> None:
        token = params["token"]
        if any(self._row_session_token(row) == token for row in self.session_rows):
            raise ValueError(f"duplicate session: {token}")
        self.session_rows.append(
            (
                token,
                params["email"],
                params["created_at"],
            )
        )

    def _delete_session_by_token(self, token: object) -> int:
        before = len(self.session_rows)
        self.session_rows = [
            row for row in self.session_rows if self._row_session_token(row) != token
        ]
        return before - len(self.session_rows)

    def _delete_sessions_by_email(self, email: object) -> int:
        before = len(self.session_rows)
        self.session_rows = [
            row for row in self.session_rows if self._row_session_email(row) != email
        ]
        return before - len(self.session_rows)

    def _session_user_rows_for_token(
        self,
        token: object,
    ) -> list[tuple[object, ...]]:
        rows: list[tuple[object, ...]] = []
        for session in self.session_rows:
            if self._row_session_token(session) != token:
                continue
            user = self._user_by_email(self._row_session_email(session))
            if user is None:
                continue
            rows.append((*user, self._row_session_created_at(session)))
        return rows

    def _active_session_rows(self) -> list[tuple[object, ...]]:
        rows: list[tuple[object, ...]] = []
        for session in self.session_rows:
            user = self._user_by_email(self._row_session_email(session))
            if user is None:
                continue
            values = {
                "token": self._row_session_token(session),
                "email": self._row_session_email(session),
                "session_created_at": self._row_session_created_at(session),
                "role": user[USER_COLUMNS.index("role")],
                "organization_id": user[USER_COLUMNS.index("organization_id")],
                "disabled_at": user[USER_COLUMNS.index("disabled_at")],
            }
            rows.append(tuple(values[column] for column in ACTIVE_SESSION_COLUMNS))
        created_at_index = ACTIVE_SESSION_COLUMNS.index("session_created_at")
        return sorted(
            rows,
            key=lambda row: str(row[created_at_index] or ""),
            reverse=True,
        )

    def _insert_model_version(self, params: dict[str, object]) -> None:
        version = params["version"]
        if any(self._row_version(row) == version for row in self.rows):
            raise ValueError(f"duplicate model version: {version}")
        self.rows.append(
            tuple(
                {
                    "version": version,
                    "model_name": params["model_name"],
                    "model_type": "logistic_regression",
                    "lifecycle_status": "candidate",
                    "is_active": False,
                    "feature_schema_version": params["feature_schema_version"],
                    "training_data_label": params["training_data_label"],
                    "random_state": params["random_state"],
                    "metrics_json": params["metrics_json"],
                    "limitations_json": params["limitations_json"],
                    "created_by": params["created_by"],
                    "created_at": params["created_at"],
                    "activated_at": None,
                }[column]
                for column in MODEL_VERSION_COLUMNS
            )
        )

    def _deactivate_other_model_versions(self, version: object) -> None:
        updated_rows: list[tuple[object, ...]] = []
        for row in self.rows:
            if self._row_is_active(row) is True and self._row_version(row) != version:
                row = self._replace_column(row, "lifecycle_status", "inactive")
                row = self._replace_column(row, "is_active", False)
            updated_rows.append(row)
        self.rows = updated_rows

    def _activate_model_version(self, params: dict[str, object]) -> None:
        updated_rows: list[tuple[object, ...]] = []
        for row in self.rows:
            if self._row_version(row) == params["version"]:
                row = self._replace_column(row, "lifecycle_status", "active")
                row = self._replace_column(row, "is_active", True)
                row = self._replace_column(row, "activated_at", params["activated_at"])
            updated_rows.append(row)
        self.rows = updated_rows

    def _insert_audit_event(self, params: dict[str, object]) -> None:
        next_id = (
            max((int(row[AUDIT_EVENT_COLUMNS.index("id")]) for row in self.audit_rows), default=0)
            + 1
        )
        self.audit_rows.append(
            tuple(
                {
                    "id": next_id,
                    "actor_email": params["actor_email"],
                    "action": params["action"],
                    "entity_type": params["entity_type"],
                    "entity_id": params["entity_id"],
                    "details_json": params["details_json"],
                    "created_at": params["created_at"],
                }[column]
                for column in AUDIT_EVENT_COLUMNS
            )
        )

    def _ordered_audit_rows(self) -> list[tuple[object, ...]]:
        id_index = AUDIT_EVENT_COLUMNS.index("id")
        return sorted(
            self.audit_rows,
            key=lambda row: int(row[id_index]),
            reverse=True,
        )

    @staticmethod
    def _row_organization_id(row: tuple[object, ...]) -> object:
        return row[ORGANIZATION_COLUMNS.index("id")]

    @staticmethod
    def _ordered_organization_rows(
        rows: list[tuple[object, ...]],
    ) -> list[tuple[object, ...]]:
        name_index = ORGANIZATION_COLUMNS.index("name")
        return sorted(rows, key=lambda row: str(row[name_index]))

    def _insert_organization(self, params: dict[str, object]) -> None:
        organization_id = params["organization_id"]
        if any(
            self._row_organization_id(row) == organization_id
            for row in self.organization_rows
        ):
            raise ValueError(f"duplicate organization: {organization_id}")
        self.organization_rows.append(
            tuple(
                {
                    "id": organization_id,
                    "name": params["name"],
                    "region": params["region"],
                    "created_at": params["created_at"],
                }[column]
                for column in ORGANIZATION_COLUMNS
            )
        )

    def _update_user_organization(self, params: dict[str, object]) -> None:
        email = str(params["email"])
        if email in self.user_organization_rows:
            self.user_organization_rows[email] = params["organization_id"]
        self._update_user_row(
            email,
            {"organization_id": params["organization_id"]},
        )

    def execute(
        self,
        sql: str,
        params: dict[str, object],
    ) -> FakePostgresCursor:
        self.query_log.append((sql, dict(params)))
        rowcount: int | None = None
        if "INSERT INTO model_versions" in sql:
            self._insert_model_version(params)
            rows: list[tuple[object, ...]] = []
            rowcount = 1
        elif "INSERT INTO users" in sql:
            self._insert_user(params)
            rows = []
            rowcount = 1
        elif "INSERT INTO sessions" in sql:
            self._insert_session(params)
            rows = []
            rowcount = 1
        elif "INSERT INTO audit_events" in sql:
            self._insert_audit_event(params)
            rows = []
            rowcount = 1
        elif "INSERT INTO mfi_organizations" in sql:
            self._insert_organization(params)
            rows = []
            rowcount = 1
        elif "DELETE FROM sessions" in sql and "WHERE token" in sql:
            rowcount = self._delete_session_by_token(params["token"])
            rows = []
        elif "DELETE FROM sessions" in sql and "WHERE email" in sql:
            rowcount = self._delete_sessions_by_email(params["email"])
            rows = []
        elif "UPDATE users" in sql and "disabled_at = %(disabled_at)s" in sql:
            rowcount = self._update_user_row(
                params["email"],
                {
                    "disabled_at": params["disabled_at"],
                    "disabled_by": params["disabled_by"],
                },
                require_null="disabled_at",
            )
            rows = []
        elif "UPDATE users" in sql and "disabled_at = NULL" in sql:
            rowcount = self._update_user_row(
                params["email"],
                {
                    "disabled_at": None,
                    "disabled_by": None,
                },
                require_not_null="disabled_at",
            )
            rows = []
        elif "UPDATE users" in sql and "mfa_attested_at = %(mfa_attested_at)s" in sql:
            rowcount = self._update_user_row(
                params["email"],
                {
                    "mfa_attested_at": params["mfa_attested_at"],
                    "mfa_attested_by": params["mfa_attested_by"],
                    "mfa_method": params["mfa_method"],
                },
                require_null="mfa_attested_at",
            )
            rows = []
        elif "UPDATE users" in sql and "SET organization_id" in sql:
            self._update_user_organization(params)
            rows = []
            rowcount = 1
        elif "FROM sessions" in sql and "WHERE sessions.token" in sql:
            rows = self._session_user_rows_for_token(params["token"])
        elif "FROM sessions" in sql and "ORDER BY sessions.created_at DESC" in sql:
            rows = self._active_session_rows()
        elif "FROM users" in sql and "ORDER BY role, email" in sql:
            rows = self._list_user_rows()
        elif "FROM users" in sql and "WHERE email = %(email)s" in sql:
            user = self._user_by_email(params["email"])
            if user is None:
                rows = []
            elif "SELECT email, disabled_at, disabled_by" in sql:
                rows = [
                    (
                        user[USER_COLUMNS.index("email")],
                        user[USER_COLUMNS.index("disabled_at")],
                        user[USER_COLUMNS.index("disabled_by")],
                    )
                ]
            elif "SELECT email, disabled_at" in sql:
                rows = [
                    (
                        user[USER_COLUMNS.index("email")],
                        user[USER_COLUMNS.index("disabled_at")],
                    )
                ]
            elif "SELECT email, mfa_attested_at" in sql:
                rows = [
                    (
                        user[USER_COLUMNS.index("email")],
                        user[USER_COLUMNS.index("mfa_attested_at")],
                    )
                ]
            else:
                rows = [user]
        elif "FROM audit_events" in sql:
            rows = self._ordered_audit_rows()
        elif "FROM mfi_organizations" in sql and "WHERE id = %(organization_id)s" in sql:
            organization_id = params["organization_id"]
            rows = [
                row
                for row in self.organization_rows
                if self._row_organization_id(row) == organization_id
            ]
        elif "FROM mfi_organizations" in sql:
            rows = self._ordered_organization_rows(self.organization_rows)
        elif "SET lifecycle_status = 'inactive', is_active = FALSE" in sql:
            self._deactivate_other_model_versions(params["version"])
            rows = []
            rowcount = 1
        elif "SET lifecycle_status = 'active', is_active = TRUE" in sql:
            self._activate_model_version(params)
            rows = []
            rowcount = 1
        elif "WHERE version = %(version)s" in sql:
            version = params["version"]
            rows = [
                row
                for row in self.rows
                if self._row_version(row) == version
            ]
        elif "WHERE is_active IS TRUE" in sql:
            rows = [
                row for row in self._ordered_rows(self.rows) if self._row_is_active(row) is True
            ][:1]
        else:
            rows = self._ordered_rows(self.rows)
        return FakePostgresCursor(rows, rowcount=rowcount)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _postgres_model_version_row(model_version: dict[str, object]) -> tuple[object, ...]:
    values = {
        "version": model_version["version"],
        "model_name": model_version["model_name"],
        "model_type": model_version["model_type"],
        "lifecycle_status": model_version["lifecycle_status"],
        "is_active": model_version["is_active"],
        "feature_schema_version": model_version["feature_schema_version"],
        "training_data_label": model_version["training_data_label"],
        "random_state": model_version["random_state"],
        "metrics_json": model_version["metrics"],
        "limitations_json": model_version["limitations"],
        "created_by": model_version["created_by"],
        "created_at": model_version["created_at"],
        "activated_at": model_version["activated_at"],
    }
    return tuple(values[column] for column in MODEL_VERSION_COLUMNS)


def _postgres_audit_event_row(event: dict[str, object]) -> tuple[object, ...]:
    values = {
        "id": event["id"],
        "actor_email": event["actor_email"],
        "action": event["action"],
        "entity_type": event["entity_type"],
        "entity_id": event["entity_id"],
        "details_json": event["details"],
        "created_at": event["created_at"],
    }
    return tuple(values[column] for column in AUDIT_EVENT_COLUMNS)


def _postgres_organization_row(organization: dict[str, object]) -> tuple[object, ...]:
    values = {
        "id": organization["id"],
        "name": organization["name"],
        "region": organization["region"],
        "created_at": organization["created_at"],
    }
    return tuple(values[column] for column in ORGANIZATION_COLUMNS)


def _postgres_user_row(user: dict[str, object]) -> tuple[object, ...]:
    values = {
        "email": user["email"],
        "password_hash": user["password_hash"],
        "role": user["role"],
        "organization_id": user["organization_id"],
        "created_at": user["created_at"],
        "disabled_at": user["disabled_at"],
        "disabled_by": user["disabled_by"],
        "mfa_attested_at": user["mfa_attested_at"],
        "mfa_attested_by": user["mfa_attested_by"],
        "mfa_method": user["mfa_method"],
    }
    return tuple(values[column] for column in USER_COLUMNS)


def _postgres_session_row(
    *,
    token: str,
    email: str,
    created_at: str,
) -> tuple[object, ...]:
    return (token, email, created_at)


class PostgresRepositoryAdapterTests(unittest.TestCase):
    def test_repository_contract_methods_exist_on_sqlite_repository(self) -> None:
        sqlite_methods = {
            name
            for name, value in inspect.getmembers(
                MicroScoreRepository,
                predicate=inspect.isfunction,
            )
            if not name.startswith("_")
        }

        for method in repository_contract_methods():
            with self.subTest(method=method):
                self.assertIn(method, sqlite_methods)

    def test_repository_contract_summary_is_partial_method_groups(self) -> None:
        summary = repository_contract_summary()

        self.assertEqual(summary["module"], POSTGRESQL_REPOSITORY_ADAPTER_MODULE)
        self.assertEqual(
            summary["version"],
            POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        )
        self.assertEqual(summary["status"], POSTGRESQL_REPOSITORY_ADAPTER_STATUS)
        self.assertEqual(summary["status"], "partial_method_groups")
        self.assertEqual(
            summary["stage"],
            "model_registry_audit_organizations_identity_groups_v1",
        )
        self.assertTrue(summary["present"])
        self.assertFalse(summary["runtime_enabled"])
        self.assertEqual(summary["method_count"], 52)
        self.assertEqual(summary["implemented_method_count"], 22)
        self.assertEqual(summary["pending_method_count"], 30)
        self.assertEqual(summary["completed_method_group_count"], 4)
        self.assertEqual(
            summary["completed_method_groups"],
            ["identity_access", "organizations", "model_registry", "audit"],
        )
        self.assertEqual(summary["read_only_method_count"], 10)
        self.assertEqual(summary["write_method_count"], 12)
        self.assertEqual(
            summary["implemented_methods"],
            [
                "create_model_version",
                "get_model_version",
                "get_active_model_version",
                "list_model_versions",
                "activate_model_version",
                "record_audit_event",
                "list_audit_events",
                "create_organization",
                "get_organization",
                "list_organizations",
                "assign_user_organization",
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
            ],
        )
        self.assertEqual(len(summary["method_groups"]), len(REPOSITORY_METHOD_GROUPS))
        group_keys = {group["key"] for group in summary["method_groups"]}
        self.assertIn("identity_access", group_keys)
        self.assertIn("staff_invites_delivery", group_keys)
        self.assertIn("application_lifecycle", group_keys)
        self.assertIn("portfolio_analytics", group_keys)
        groups = {group["key"]: group for group in summary["method_groups"]}
        self.assertEqual(groups["model_registry"]["implemented_method_count"], 5)
        self.assertEqual(groups["model_registry"]["pending_method_count"], 0)
        self.assertFalse(groups["model_registry"]["pending_methods"])
        self.assertEqual(groups["audit"]["implemented_method_count"], 2)
        self.assertEqual(groups["audit"]["pending_method_count"], 0)
        self.assertFalse(groups["audit"]["pending_methods"])
        self.assertEqual(groups["organizations"]["implemented_method_count"], 4)
        self.assertEqual(groups["organizations"]["pending_method_count"], 0)
        self.assertFalse(groups["organizations"]["pending_methods"])
        self.assertEqual(groups["identity_access"]["implemented_method_count"], 11)
        self.assertEqual(groups["identity_access"]["pending_method_count"], 0)
        self.assertFalse(groups["identity_access"]["pending_methods"])
        self.assertIn(
            "model registry, audit, organization, and identity/session",
            summary["limitation"],
        )

    def test_model_registry_read_adapter_matches_sqlite_repository_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_repository = MicroScoreRepository(Path(tmpdir) / "microscore.sqlite3")
            sqlite_repository.create_model_version(
                version="candidate-v0.2",
                model_name="Candidate Logistic Regression",
                feature_schema_version="behavioral-v2",
                training_data_label="synthetic-credit-risk-v2",
                random_state=99,
                metrics={"roc_auc": 0.82, "brier_score": 0.14},
                limitations=["candidate parity fixture"],
                created_by="admin@example.com",
            )

            sqlite_versions = sqlite_repository.list_model_versions()
            postgres_rows = [
                _postgres_model_version_row(model_version)
                for model_version in sqlite_versions
            ]
            query_log: list[tuple[str, dict[str, object]]] = []
            fake_connection = FakePostgresConnection(postgres_rows, query_log)
            adapter = PostgresRepositoryAdapter(lambda: fake_connection)

            self.assertEqual(
                adapter.get_active_model_version(),
                sqlite_repository.get_active_model_version(),
            )
            self.assertEqual(
                adapter.get_model_version("candidate-v0.2"),
                sqlite_repository.get_model_version("candidate-v0.2"),
            )
            self.assertEqual(
                adapter.list_model_versions(),
                sqlite_versions,
            )
            self.assertEqual(
                model_registry_read_parity_snapshot(adapter),
                model_registry_read_parity_snapshot(sqlite_repository),
            )
            self.assertTrue(fake_connection.closed)
            self.assertTrue(
                any("%(version)s" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("WHERE is_active IS TRUE" in sql for sql, _params in query_log)
            )

    def test_model_registry_write_adapter_matches_sqlite_repository_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_repository = MicroScoreRepository(Path(tmpdir) / "microscore.sqlite3")
            postgres_rows = [
                _postgres_model_version_row(model_version)
                for model_version in sqlite_repository.list_model_versions()
            ]
            query_log: list[tuple[str, dict[str, object]]] = []
            fake_connection = FakePostgresConnection(postgres_rows, query_log)
            adapter = PostgresRepositoryAdapter(lambda: fake_connection)
            payload = {
                "version": "candidate-v0.3",
                "model_name": "Candidate Logistic Regression",
                "feature_schema_version": "behavioral-v3",
                "training_data_label": "synthetic-credit-risk-v3",
                "random_state": 123,
                "metrics": {"roc_auc": 0.83, "brier_score": 0.13},
                "limitations": ["write parity fixture"],
                "created_by": "admin@example.com",
            }

            sqlite_created = sqlite_repository.create_model_version(**payload)
            postgres_created = adapter.create_model_version(**payload)
            for key in (
                "version",
                "model_name",
                "model_type",
                "lifecycle_status",
                "is_active",
                "feature_schema_version",
                "training_data_label",
                "random_state",
                "metrics",
                "limitations",
                "created_by",
                "activated_at",
            ):
                self.assertEqual(postgres_created[key], sqlite_created[key])

            sqlite_activated = sqlite_repository.activate_model_version(
                "candidate-v0.3"
            )
            postgres_activated = adapter.activate_model_version("candidate-v0.3")

            self.assertEqual(postgres_activated["version"], sqlite_activated["version"])
            self.assertTrue(postgres_activated["is_active"])
            self.assertEqual(postgres_activated["lifecycle_status"], "active")
            self.assertEqual(
                model_registry_method_group_parity_snapshot(adapter),
                model_registry_method_group_parity_snapshot(sqlite_repository),
            )
            self.assertIsNone(adapter.activate_model_version("missing-version"))
            self.assertGreaterEqual(fake_connection.commits, 2)
            self.assertEqual(fake_connection.rollbacks, 0)
            self.assertTrue(
                any("INSERT INTO model_versions" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("is_active = FALSE" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("is_active = TRUE" in sql for sql, _params in query_log)
            )

    def test_audit_adapter_matches_sqlite_repository_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_repository = MicroScoreRepository(Path(tmpdir) / "microscore.sqlite3")
            sqlite_repository.record_audit_event(
                actor_email="admin@example.com",
                action="model_version_created",
                entity_type="model_version",
                entity_id="candidate-v0.3",
                details={
                    "version": "candidate-v0.3",
                    "source": "sqlite-parity",
                },
            )
            sqlite_repository.record_audit_event(
                actor_email=None,
                action="system_storage_checked",
                entity_type="storage",
                entity_id=None,
                details={"backend": "sqlite", "status": "ready"},
            )
            sqlite_events = sqlite_repository.list_audit_events()
            postgres_audit_rows = [
                _postgres_audit_event_row(event)
                for event in sqlite_events
            ]
            query_log: list[tuple[str, dict[str, object]]] = []
            fake_connection = FakePostgresConnection([], query_log, postgres_audit_rows)
            adapter = PostgresRepositoryAdapter(lambda: fake_connection)

            self.assertEqual(adapter.list_audit_events(), sqlite_events)
            adapter.record_audit_event(
                actor_email="admin@example.com",
                action="adapter_audit_smoke",
                entity_type="postgres_repository",
                entity_id="audit",
                details={"method_group": "audit", "complete": True},
            )
            sqlite_repository.record_audit_event(
                actor_email="admin@example.com",
                action="adapter_audit_smoke",
                entity_type="postgres_repository",
                entity_id="audit",
                details={"method_group": "audit", "complete": True},
            )

            self.assertEqual(
                audit_method_group_parity_snapshot(adapter),
                audit_method_group_parity_snapshot(sqlite_repository),
            )
            self.assertGreaterEqual(fake_connection.commits, 1)
            self.assertEqual(fake_connection.rollbacks, 0)
            self.assertTrue(
                any("INSERT INTO audit_events" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("ORDER BY id DESC" in sql for sql, _params in query_log)
            )

    def test_organization_adapter_matches_sqlite_repository_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_repository = MicroScoreRepository(Path(tmpdir) / "microscore.sqlite3")
            sqlite_repository.create_organization(
                organization_id="pavlodar-zeta-mfi",
                name="Zeta Pavlodar MFI",
                region="Pavlodar",
            )
            sqlite_repository.create_organization(
                organization_id="pavlodar-aksu-mfi",
                name="Aksu Pavlodar MFI",
                region="Aksu",
            )
            sqlite_repository.create_user(
                "tenant-analyst@example.com",
                "hash",
                "mfi_analyst",
            )

            sqlite_organizations = sqlite_repository.list_organizations()
            postgres_organization_rows = [
                _postgres_organization_row(organization)
                for organization in sqlite_organizations
            ]
            query_log: list[tuple[str, dict[str, object]]] = []
            fake_connection = FakePostgresConnection(
                [],
                query_log,
                organization_rows=postgres_organization_rows,
                user_organization_rows={"tenant-analyst@example.com": None},
            )
            adapter = PostgresRepositoryAdapter(lambda: fake_connection)

            self.assertEqual(
                adapter.get_organization("pavlodar-aksu-mfi"),
                sqlite_repository.get_organization("pavlodar-aksu-mfi"),
            )
            self.assertEqual(adapter.list_organizations(), sqlite_organizations)

            payload = {
                "organization_id": "pavlodar-second-mfi",
                "name": "Second Pavlodar MFI",
                "region": "Pavlodar region",
            }
            sqlite_created = sqlite_repository.create_organization(**payload)
            postgres_created = adapter.create_organization(**payload)
            for key in ("id", "name", "region"):
                self.assertEqual(postgres_created[key], sqlite_created[key])

            sqlite_repository.assign_user_organization(
                "tenant-analyst@example.com",
                "pavlodar-second-mfi",
            )
            adapter.assign_user_organization(
                "tenant-analyst@example.com",
                "pavlodar-second-mfi",
            )
            self.assertEqual(
                fake_connection.user_organization_rows["tenant-analyst@example.com"],
                sqlite_repository.get_user("tenant-analyst@example.com")[
                    "organization_id"
                ],
            )

            sqlite_repository.assign_user_organization(
                "tenant-analyst@example.com",
                None,
            )
            adapter.assign_user_organization("tenant-analyst@example.com", None)
            self.assertIsNone(
                fake_connection.user_organization_rows["tenant-analyst@example.com"]
            )
            self.assertIsNone(
                sqlite_repository.get_user("tenant-analyst@example.com")[
                    "organization_id"
                ]
            )
            self.assertEqual(
                organization_method_group_parity_snapshot(adapter),
                organization_method_group_parity_snapshot(sqlite_repository),
            )
            self.assertGreaterEqual(fake_connection.commits, 3)
            self.assertEqual(fake_connection.rollbacks, 0)
            self.assertTrue(
                any("INSERT INTO mfi_organizations" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("FROM mfi_organizations" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("UPDATE users" in sql and "organization_id" in sql for sql, _params in query_log)
            )
            self.assertTrue(
                any("ORDER BY name" in sql for sql, _params in query_log)
            )

    def test_identity_access_adapter_matches_sqlite_repository_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_repository = MicroScoreRepository(Path(tmpdir) / "microscore.sqlite3")
            fixed_now = datetime.now(timezone.utc).replace(microsecond=0)
            active_created_at = (fixed_now - timedelta(minutes=30)).isoformat()
            borrower_created_at = (fixed_now - timedelta(minutes=20)).isoformat()
            expired_created_at = (fixed_now - timedelta(hours=3)).isoformat()
            disabled_created_at = (fixed_now - timedelta(minutes=10)).isoformat()
            sqlite_repository.create_organization(
                organization_id="identity-mfi",
                name="Identity MFI",
                region="Pavlodar",
            )
            query_log: list[tuple[str, dict[str, object]]] = []
            fake_connection = FakePostgresConnection([], query_log)
            adapter = PostgresRepositoryAdapter(lambda: fake_connection)

            user_payloads = [
                ("identity-admin@example.com", "admin-hash", "admin", None),
                (
                    "identity-analyst@example.com",
                    "analyst-hash",
                    "mfi_analyst",
                    "identity-mfi",
                ),
                ("identity-borrower@example.com", "borrower-hash", "borrower", None),
                (
                    "identity-disabled@example.com",
                    "disabled-hash",
                    "mfi_analyst",
                    "identity-mfi",
                ),
            ]
            for email, password_hash, role, organization_id in user_payloads:
                sqlite_created = sqlite_repository.create_user(
                    email,
                    password_hash,
                    role,
                    organization_id,
                )
                postgres_created = adapter.create_user(
                    email,
                    password_hash,
                    role,
                    organization_id,
                )
                for key in ("email", "password_hash", "role", "organization_id"):
                    self.assertEqual(postgres_created[key], sqlite_created[key])

            sqlite_attested = sqlite_repository.attest_user_mfa(
                "identity-analyst@example.com",
                "identity-admin@example.com",
                "totp",
            )
            postgres_attested = adapter.attest_user_mfa(
                "identity-analyst@example.com",
                "identity-admin@example.com",
                "totp",
            )
            self.assertEqual(postgres_attested["mfa_method"], sqlite_attested["mfa_method"])
            self.assertFalse(postgres_attested["was_already_attested"])
            self.assertTrue(
                adapter.attest_user_mfa(
                    "identity-analyst@example.com",
                    "identity-admin@example.com",
                    "totp",
                )["was_already_attested"]
            )
            self.assertIsNone(adapter.attest_user_mfa("missing@example.com", "admin", "totp"))

            for repository in (sqlite_repository, adapter):
                self.assertEqual(
                    repository.create_session(
                        "identity-analyst-token",
                        "identity-analyst@example.com",
                        created_at=active_created_at,
                    )["session_ttl_seconds"],
                    28_800,
                )
                repository.create_session(
                    "identity-borrower-token",
                    "identity-borrower@example.com",
                    created_at=borrower_created_at,
                )
                repository.create_session(
                    "identity-expired-token",
                    "identity-admin@example.com",
                    created_at=expired_created_at,
                )
                repository.create_session(
                    "identity-disabled-token",
                    "identity-disabled@example.com",
                    created_at=disabled_created_at,
                )

            sqlite_disabled = sqlite_repository.disable_user(
                "identity-disabled@example.com",
                "identity-admin@example.com",
            )
            postgres_disabled = adapter.disable_user(
                "identity-disabled@example.com",
                "identity-admin@example.com",
            )
            self.assertEqual(postgres_disabled["revoked_session_count"], 1)
            self.assertEqual(
                postgres_disabled["revoked_session_count"],
                sqlite_disabled["revoked_session_count"],
            )
            self.assertFalse(postgres_disabled["was_already_disabled"])
            self.assertTrue(
                adapter.disable_user(
                    "identity-disabled@example.com",
                    "identity-admin@example.com",
                )["was_already_disabled"]
            )
            self.assertIsNone(adapter.disable_user("missing@example.com", "admin"))

            sqlite_reactivated = sqlite_repository.reactivate_user(
                "identity-disabled@example.com"
            )
            postgres_reactivated = adapter.reactivate_user(
                "identity-disabled@example.com"
            )
            self.assertFalse(postgres_reactivated["was_already_active"])
            self.assertIsNotNone(postgres_reactivated["previous_disabled_at"])
            self.assertEqual(
                postgres_reactivated["previous_disabled_by"],
                sqlite_reactivated["previous_disabled_by"],
            )
            self.assertTrue(
                adapter.reactivate_user("identity-disabled@example.com")[
                    "was_already_active"
                ]
            )
            self.assertIsNone(adapter.reactivate_user("missing@example.com"))

            sqlite_active_user = sqlite_repository.get_user_by_token(
                "identity-analyst-token",
                now=fixed_now,
                ttl_hours=1,
            )
            postgres_active_user = adapter.get_user_by_token(
                "identity-analyst-token",
                now=fixed_now,
                ttl_hours=1,
            )
            self.assertEqual(postgres_active_user["email"], sqlite_active_user["email"])
            self.assertEqual(
                postgres_active_user["session_expires_at"],
                sqlite_active_user["session_expires_at"],
            )
            self.assertIsNone(
                adapter.get_user_by_token(
                    "identity-expired-token",
                    now=fixed_now,
                    ttl_hours=1,
                )
            )
            self.assertIsNone(
                sqlite_repository.get_user_by_token(
                    "identity-expired-token",
                    now=fixed_now,
                    ttl_hours=1,
                )
            )

            self.assertEqual(
                identity_access_method_group_parity_snapshot(
                    adapter,
                    now=fixed_now,
                    ttl_hours=1,
                ),
                identity_access_method_group_parity_snapshot(
                    sqlite_repository,
                    now=fixed_now,
                    ttl_hours=1,
                ),
            )
            active_sessions = adapter.list_active_sessions(
                now=fixed_now,
                ttl_hours=1,
            )
            borrower_session = next(
                session
                for session in active_sessions
                if session["email"] == "identity-borrower@example.com"
            )
            self.assertIsNone(
                adapter.revoke_session_by_id(
                    borrower_session["session_id"],
                    staff_only=True,
                )
            )
            sqlite_borrower_session = next(
                session
                for session in sqlite_repository.list_active_sessions(
                    now=fixed_now,
                    ttl_hours=1,
                )
                if session["email"] == "identity-borrower@example.com"
            )
            self.assertIsNone(
                sqlite_repository.revoke_session_by_id(
                    sqlite_borrower_session["session_id"],
                    staff_only=True,
                )
            )
            analyst_session = next(
                session
                for session in active_sessions
                if session["email"] == "identity-analyst@example.com"
            )
            sqlite_analyst_session = next(
                session
                for session in sqlite_repository.list_active_sessions(
                    now=fixed_now,
                    ttl_hours=1,
                )
                if session["email"] == "identity-analyst@example.com"
            )
            self.assertEqual(
                adapter.revoke_session_by_id(
                    analyst_session["session_id"],
                    staff_only=True,
                )["email"],
                sqlite_repository.revoke_session_by_id(
                    sqlite_analyst_session["session_id"],
                    staff_only=True,
                )["email"],
            )
            self.assertTrue(adapter.revoke_session("identity-borrower-token"))
            self.assertTrue(sqlite_repository.revoke_session("identity-borrower-token"))
            self.assertFalse(adapter.revoke_session("identity-borrower-token"))

            self.assertEqual(
                identity_access_method_group_parity_snapshot(
                    adapter,
                    now=fixed_now,
                    ttl_hours=1,
                ),
                identity_access_method_group_parity_snapshot(
                    sqlite_repository,
                    now=fixed_now,
                    ttl_hours=1,
                ),
            )
            self.assertGreaterEqual(fake_connection.commits, 10)
            self.assertEqual(fake_connection.rollbacks, 0)
            self.assertTrue(any("INSERT INTO users" in sql for sql, _params in query_log))
            self.assertTrue(any("INSERT INTO sessions" in sql for sql, _params in query_log))
            self.assertTrue(any("DELETE FROM sessions" in sql for sql, _params in query_log))
            self.assertTrue(any("mfa_attested_at" in sql for sql, _params in query_log))
            self.assertTrue(any("disabled_at" in sql for sql, _params in query_log))
            self.assertTrue(
                any("ORDER BY sessions.created_at DESC" in sql for sql, _params in query_log)
            )

    def test_partial_adapter_refuses_runtime_without_connection_factory(self) -> None:
        adapter = PostgresRepositoryAdapter()

        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.list_model_versions()
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.create_model_version(
                version="candidate-v0.4",
                model_name="Candidate",
                feature_schema_version="behavioral-v4",
                training_data_label="synthetic-credit-risk-v4",
                random_state=7,
                metrics={},
                limitations=[],
                created_by="admin@example.com",
            )
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.activate_model_version("research-v0.1")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.record_audit_event(
                actor_email=None,
                action="blocked_without_connection",
                entity_type="postgres_repository",
                entity_id=None,
                details={},
            )
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.list_audit_events()
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.create_organization(
                organization_id="blocked-mfi",
                name="Blocked MFI",
                region="Pavlodar",
            )
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.get_organization("blocked-mfi")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.list_organizations()
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.assign_user_organization("blocked@example.com", "blocked-mfi")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.create_user("blocked@example.com", "hash", "admin")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.get_user("blocked@example.com")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.list_users()
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.disable_user("blocked@example.com", "admin@example.com")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.reactivate_user("blocked@example.com")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.attest_user_mfa("blocked@example.com", "admin@example.com", "totp")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.create_session("blocked-token", "blocked@example.com")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.get_user_by_token("blocked-token")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.list_active_sessions()
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.revoke_session("blocked-token")
        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.revoke_session_by_id("blocked-session-id")

    def test_adapter_skeleton_refuses_runtime_connection(self) -> None:
        adapter = PostgresRepositoryAdapterSkeleton()
        contract = adapter.describe_contract()

        self.assertEqual(adapter.backend, "postgresql")
        self.assertEqual(contract["database_url_env"], "MICROSCORE_DATABASE_URL")
        self.assertFalse(contract["runtime_enabled"])
        with self.assertRaisesRegex(RuntimeError, "runtime is disabled"):
            adapter.connect()


if __name__ == "__main__":
    unittest.main()
