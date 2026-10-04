from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "postgresql-backup-restore-smoke.py"


class PostgresqlRecoverySmokeTests(unittest.TestCase):
    def test_dry_run_exposes_recovery_contract(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--dry-run"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "postgresql-backup-restore-smoke-dry-run")
        self.assertEqual(payload["schema_version"], "0001_initial_schema")
        self.assertEqual(payload["tables_verified"], 12)
        self.assertEqual(
            payload["required_binaries"],
            ["pg_dump", "pg_restore", "createdb", "dropdb", "psql"],
        )
        self.assertEqual(payload["comparison"], "row-count-and-full-row-fingerprint")
        self.assertTrue(payload["temporary_restore_database"])
        self.assertTrue(payload["cleanup_required"])
        self.assertFalse(payload["credentials_in_command_arguments"])
        self.assertFalse(payload["production_ready"])

    def test_script_verifies_content_and_cleans_up(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("pg_dump", script)
        self.assertIn("pg_restore", script)
        self.assertIn("createdb", script)
        self.assertIn("dropdb", script)
        self.assertIn("row_to_json", script)
        self.assertIn("string_agg", script)
        self.assertIn("fingerprints_match", script)
        self.assertIn("restore_database_dropped", script)
        self.assertIn("finally:", script)
        self.assertIn("WHERE is_active IS TRUE", script)
        self.assertIn("schema_migrations", script)
        self.assertIn("TemporaryDirectory", script)

    def test_script_keeps_database_credentials_out_of_arguments_and_output(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("PGPASSWORD", script)
        self.assertIn("[DATABASE_URL_REDACTED]", script)
        self.assertIn("[PASSWORD_REDACTED]", script)
        self.assertIn("credentials_in_output", script)
        self.assertNotIn('"--dbname",\n                    database_url', script)
        self.assertNotIn("print(database_url", script)


if __name__ == "__main__":
    unittest.main()
