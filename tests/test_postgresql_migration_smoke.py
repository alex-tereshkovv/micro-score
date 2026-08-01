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
        self.assertEqual(payload["expected_model_registry_read_methods"], 3)
        self.assertEqual(payload["expected_model_registry_write_methods"], 2)
        self.assertEqual(payload["expected_model_registry_methods"], 5)
        self.assertEqual(payload["expected_audit_methods"], 2)
        self.assertEqual(payload["expected_organization_methods"], 4)
        self.assertEqual(payload["expected_identity_methods"], 11)
        self.assertEqual(payload["expected_staff_invite_methods"], 15)
        self.assertEqual(payload["expected_application_lifecycle_methods"], 10)

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
        self.assertIn("WHERE is_active IS TRUE", script)
        self.assertIn("metrics_json->>'roc_auc'", script)
        self.assertIn("model_registry_active_version", script)
        self.assertIn("ci-smoke-model-candidate", script)
        self.assertIn("model_registry_write_methods", script)
        self.assertIn("postgresql_audit_adapter_smoke", script)
        self.assertIn("audit_latest_action", script)
        self.assertIn("details_json->>'method_group'", script)
        self.assertIn("POSTGRESQL_ORGANIZATION_METHODS", script)
        self.assertIn("organization_directory", script)
        self.assertIn("organization_assignment", script)
        self.assertIn("POSTGRESQL_IDENTITY_METHODS", script)
        self.assertIn("identity_mfa_method", script)
        self.assertIn("identity_session_scope", script)
        self.assertIn("identity_disabled_by", script)
        self.assertIn("identity_revoked_session_count", script)
        self.assertIn("POSTGRESQL_STAFF_INVITE_METHODS", script)
        self.assertIn("staff_invite_methods", script)
        self.assertIn("staff_invite_delivery", script)
        self.assertIn("staff_invite_attempt_status", script)
        self.assertIn("staff_invite_event_metadata", script)
        self.assertIn("metadata_json->>'message_id'", script)
        self.assertIn("POSTGRESQL_APPLICATION_LIFECYCLE_METHODS", script)
        self.assertIn("application_lifecycle_methods", script)
        self.assertIn("application_lifecycle_status", script)
        self.assertIn("application_decision_count", script)
        self.assertIn("application_latest_decision", script)
        self.assertIn("application_timeline_latest_action", script)
        self.assertIn("application_decisions", script)
        self.assertIn("application_decision_recorded", script)
        self.assertIn("ci-smoke-active-session", script)
        self.assertIn("ci-smoke-revoked-session", script)
        self.assertIn("UPDATE users", script)
        self.assertIn("::error title=PostgreSQL migration smoke failed::", script)
        self.assertIn("psql failed with exit code", script)
        self.assertNotIn("print(database_url", script)


if __name__ == "__main__":
    unittest.main()
