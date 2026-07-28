from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PostgresqlMigrationSmokeTests(unittest.TestCase):
    def test_postgresql_migration_smoke_dry_run_validates_contract(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "postgresql-migration-smoke.py"),
                "--dry-run",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "postgresql-migration-smoke-dry-run")
        self.assertEqual(payload["version"], "0001_initial_schema")
        self.assertEqual(
            payload["migration"],
            "migrations/postgresql/0001_initial_schema.sql",
        )
        self.assertEqual(payload["expected_tables"], 12)
        self.assertEqual(payload["expected_jsonb_columns"], 8)
        self.assertEqual(payload["expected_tenant_indexes"], 4)

    def test_postgresql_migration_smoke_script_uses_psql_without_secret_logging(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "postgresql-migration-smoke.py").read_text(
            encoding="utf-8",
        )

        self.assertIn("MICROSCORE_DATABASE_URL", script)
        self.assertIn("psql", script)
        self.assertIn("--no-psqlrc", script)
        self.assertIn("ON_ERROR_STOP=1", script)
        self.assertIn("information_schema.tables", script)
        self.assertIn("information_schema.columns", script)
        self.assertIn("pg_indexes", script)
        self.assertIn("score_result_json->>'risk_band'", script)
        self.assertIn("::error title=PostgreSQL migration smoke failed::", script)
        self.assertIn("psql failed with exit code", script)
        self.assertNotIn("print(database_url", script)


if __name__ == "__main__":
    unittest.main()
