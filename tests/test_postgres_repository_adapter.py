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

    def execute(
        self,
        sql: str,
        params: dict[str, object],
    ) -> FakePostgresCursor:
        self.query_log.append((sql, dict(params)))
        if "WHERE version = %(version)s" in sql:
            version = params["version"]
            rows = [
                row
                for row in self.rows
                if row[MODEL_VERSION_COLUMNS.index("version")] == version
            ]
        elif "WHERE is_active IS TRUE" in sql:
            rows = [
                row
                for row in self.rows
                if row[MODEL_VERSION_COLUMNS.index("is_active")] is True
            ][:1]
        else:
            rows = list(self.rows)
        return FakePostgresCursor(rows)

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

    def test_repository_contract_summary_is_partial_read_only(self) -> None:
        summary = repository_contract_summary()

        self.assertEqual(summary["module"], POSTGRESQL_REPOSITORY_ADAPTER_MODULE)
        self.assertEqual(
            summary["version"],
            POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        )
        self.assertEqual(summary["status"], POSTGRESQL_REPOSITORY_ADAPTER_STATUS)
        self.assertEqual(summary["status"], "partial_read_only")
        self.assertEqual(summary["stage"], "model_registry_read_path_v1")
        self.assertTrue(summary["present"])
        self.assertFalse(summary["runtime_enabled"])
        self.assertEqual(summary["method_count"], 52)
        self.assertEqual(summary["implemented_method_count"], 3)
        self.assertEqual(summary["pending_method_count"], 49)
        self.assertEqual(summary["read_only_method_count"], 3)
        self.assertEqual(
            summary["implemented_methods"],
            [
                "get_model_version",
                "get_active_model_version",
                "list_model_versions",
            ],
        )
        self.assertEqual(len(summary["method_groups"]), len(REPOSITORY_METHOD_GROUPS))
        group_keys = {group["key"] for group in summary["method_groups"]}
        self.assertIn("identity_access", group_keys)
        self.assertIn("staff_invites_delivery", group_keys)
        self.assertIn("application_lifecycle", group_keys)
        self.assertIn("portfolio_analytics", group_keys)
        groups = {group["key"]: group for group in summary["method_groups"]}
        self.assertEqual(groups["model_registry"]["implemented_method_count"], 3)
        self.assertEqual(groups["model_registry"]["pending_method_count"], 2)
        self.assertIn("create_model_version", groups["model_registry"]["pending_methods"])
        self.assertIn("read-only model registry path", summary["limitation"])

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

    def test_partial_adapter_refuses_runtime_and_write_methods(self) -> None:
        adapter = PostgresRepositoryAdapter()

        with self.assertRaisesRegex(RuntimeError, "connection_factory"):
            adapter.list_model_versions()
        with self.assertRaisesRegex(NotImplementedError, "read-only model registry"):
            adapter.create_model_version()
        with self.assertRaisesRegex(NotImplementedError, "write methods"):
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
