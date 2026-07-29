from __future__ import annotations

import inspect
import tempfile
import unittest

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import MicroScoreRepository  # noqa: E402
from microscore_api.postgres_repository import (  # noqa: E402
    MODEL_VERSION_COLUMNS,
    POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
    POSTGRESQL_REPOSITORY_ADAPTER_MODULE,
    POSTGRESQL_REPOSITORY_ADAPTER_STATUS,
    PostgresRepositoryAdapter,
    PostgresRepositoryAdapterSkeleton,
    REPOSITORY_METHOD_GROUPS,
    model_registry_method_group_parity_snapshot,
    model_registry_read_parity_snapshot,
    repository_contract_methods,
    repository_contract_summary,
)


class FakePostgresCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

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
    ) -> None:
        self.rows = rows
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

    def execute(
        self,
        sql: str,
        params: dict[str, object],
    ) -> FakePostgresCursor:
        self.query_log.append((sql, dict(params)))
        if "INSERT INTO model_versions" in sql:
            self._insert_model_version(params)
            rows: list[tuple[object, ...]] = []
        elif "SET lifecycle_status = 'inactive', is_active = FALSE" in sql:
            self._deactivate_other_model_versions(params["version"])
            rows = []
        elif "SET lifecycle_status = 'active', is_active = TRUE" in sql:
            self._activate_model_version(params)
            rows = []
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
        return FakePostgresCursor(rows)

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

    def test_repository_contract_summary_is_partial_method_group(self) -> None:
        summary = repository_contract_summary()

        self.assertEqual(summary["module"], POSTGRESQL_REPOSITORY_ADAPTER_MODULE)
        self.assertEqual(
            summary["version"],
            POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        )
        self.assertEqual(summary["status"], POSTGRESQL_REPOSITORY_ADAPTER_STATUS)
        self.assertEqual(summary["status"], "partial_method_group")
        self.assertEqual(summary["stage"], "model_registry_method_group_v1")
        self.assertTrue(summary["present"])
        self.assertFalse(summary["runtime_enabled"])
        self.assertEqual(summary["method_count"], 52)
        self.assertEqual(summary["implemented_method_count"], 5)
        self.assertEqual(summary["pending_method_count"], 47)
        self.assertEqual(summary["completed_method_group_count"], 1)
        self.assertEqual(summary["completed_method_groups"], ["model_registry"])
        self.assertEqual(summary["read_only_method_count"], 3)
        self.assertEqual(summary["write_method_count"], 2)
        self.assertEqual(
            summary["implemented_methods"],
            [
                "create_model_version",
                "get_model_version",
                "get_active_model_version",
                "list_model_versions",
                "activate_model_version",
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
        self.assertIn("model registry method group", summary["limitation"])

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
