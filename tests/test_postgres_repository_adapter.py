from __future__ import annotations

import inspect
import unittest

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import MicroScoreRepository  # noqa: E402
from microscore_api.postgres_repository import (  # noqa: E402
    POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
    POSTGRESQL_REPOSITORY_ADAPTER_MODULE,
    POSTGRESQL_REPOSITORY_ADAPTER_STATUS,
    PostgresRepositoryAdapterSkeleton,
    REPOSITORY_METHOD_GROUPS,
    repository_contract_methods,
    repository_contract_summary,
)


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

    def test_repository_contract_summary_is_contract_only(self) -> None:
        summary = repository_contract_summary()

        self.assertEqual(summary["module"], POSTGRESQL_REPOSITORY_ADAPTER_MODULE)
        self.assertEqual(
            summary["version"],
            POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        )
        self.assertEqual(summary["status"], POSTGRESQL_REPOSITORY_ADAPTER_STATUS)
        self.assertTrue(summary["present"])
        self.assertFalse(summary["runtime_enabled"])
        self.assertEqual(summary["method_count"], 52)
        self.assertEqual(len(summary["method_groups"]), len(REPOSITORY_METHOD_GROUPS))
        group_keys = {group["key"] for group in summary["method_groups"]}
        self.assertIn("identity_access", group_keys)
        self.assertIn("staff_invites_delivery", group_keys)
        self.assertIn("application_lifecycle", group_keys)
        self.assertIn("portfolio_analytics", group_keys)
        self.assertIn("runtime guardrails", summary["limitation"])

    def test_adapter_skeleton_refuses_runtime_connection(self) -> None:
        adapter = PostgresRepositoryAdapterSkeleton()
        contract = adapter.describe_contract()

        self.assertEqual(adapter.backend, "postgresql")
        self.assertEqual(contract["database_url_env"], "MICROSCORE_DATABASE_URL")
        self.assertFalse(contract["runtime_enabled"])
        with self.assertRaisesRegex(RuntimeError, "contract-only"):
            adapter.connect()


if __name__ == "__main__":
    unittest.main()
