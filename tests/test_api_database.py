from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import (
    DuplicateModelVersionError,
    DuplicateUserError,
    InvalidApplicationTransitionError,
    JSON_TEXT_COLUMNS,
    MicroScoreRepository,
    POSTGRESQL_TENANT_SCOPE_INDEXES,
    REQUIRED_SCHEMA_TABLES,
    UnsupportedStorageBackendError,
)


class ApiDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "microscore-test.sqlite3"
        self.repository = MicroScoreRepository(self.db_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_users_sessions_and_applications_persist(self) -> None:
        self.repository.create_user(
            "borrower@example.com",
            "password-hash",
            "borrower",
        )
        self.repository.create_session("token-1", "borrower@example.com")
        application = self.repository.create_application(
            application_id="app-1",
            borrower_email="borrower@example.com",
            requested_amount=250_000,
            purpose="working capital",
            district="Pavlodar city",
            settlement_type="urban",
            behavioral_signals={
                "gender": "Female",
                "employment_status": "Self-employed",
                "loan_application_amount": 250_000,
            },
        )

        reopened = MicroScoreRepository(self.db_path)

        self.assertEqual(reopened.get_user_by_token("token-1")["email"], "borrower@example.com")
        self.assertEqual(reopened.get_application(application["id"])["district"], "Pavlodar city")
        self.assertEqual(len(reopened.list_applications()), 1)

    def test_legacy_database_is_migrated_without_deleting_tables(self) -> None:
        legacy_path = Path(self.tempdir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE users (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE loan_applications (
                    id TEXT PRIMARY KEY,
                    borrower_email TEXT NOT NULL,
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
                INSERT INTO users VALUES (
                    'legacy@example.com', 'hash', 'borrower', '2026-01-01T00:00:00+00:00'
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = MicroScoreRepository(legacy_path)

        self.assertIn("organization_id", migrated.get_user("legacy@example.com"))
        self.assertIsNone(migrated.get_user("legacy@example.com")["organization_id"])
        migrated.create_organization(
            organization_id="legacy-mfi",
            name="Legacy MFI",
            region="Pavlodar region",
        )
        migrated.assign_user_organization("legacy@example.com", "legacy-mfi")
        self.assertEqual(
            migrated.get_user("legacy@example.com")["organization_id"],
            "legacy-mfi",
        )

    def test_storage_readiness_describes_sqlite_contract(self) -> None:
        readiness = self.repository.storage_readiness()

        self.assertEqual(readiness["backend"], "sqlite")
        self.assertEqual(readiness["status"], "ready")
        self.assertFalse(readiness["production_ready"])
        self.assertEqual(readiness["database_path"], str(self.db_path))
        self.assertTrue(readiness["database_exists"])
        self.assertIn("sessions", readiness["required_tables"])
        self.assertIn("staff_invites", readiness["required_tables"])
        self.assertIn("staff_invite_delivery_events", readiness["required_tables"])
        self.assertIn("portfolio_simulations", readiness["required_tables"])
        self.assertIn("audit_events.details_json", readiness["json_columns"])
        self.assertIn(
            "staff_invite_delivery_events.metadata_json",
            readiness["json_columns"],
        )
        self.assertIn(
            "loan_applications.organization_id",
            readiness["tenant_scoped_tables"],
        )
        capability_ids = {item["id"] for item in readiness["capabilities"]}
        self.assertIn("sqlite_idempotent_startup_migrations", capability_ids)
        self.assertIn("postgresql_repository_backend", capability_ids)
        self.assertIn("postgresql_repository_adapter_contract", capability_ids)
        self.assertIn("postgresql_model_registry_read_adapter", capability_ids)
        self.assertIn("postgresql_model_registry_method_group_adapter", capability_ids)
        self.assertIn("postgresql_audit_method_group_adapter", capability_ids)
        self.assertIn("postgresql_organization_method_group_adapter", capability_ids)
        self.assertIn("postgresql_identity_access_method_group_adapter", capability_ids)
        self.assertEqual(readiness["postgresql_migration_status"], "planned")
        self.assertTrue(
            any("PostgreSQL" in item for item in readiness["postgresql_migration_checklist"])
        )

    def test_postgresql_migration_readiness_exposes_schema_inventory_and_blockers(self) -> None:
        readiness = self.repository.postgresql_migration_readiness()

        self.assertEqual(readiness["status"], "blocked")
        self.assertEqual(readiness["runtime_backend"], "sqlite")
        self.assertEqual(readiness["target_backend"], "postgresql")
        self.assertEqual(readiness["repository_backend_status"], "not_implemented")
        self.assertFalse(readiness["migration_ready"])
        self.assertFalse(readiness["production_ready"])
        self.assertFalse(readiness["live_connection_tested"])
        self.assertIn("MICROSCORE_DATABASE_URL", readiness["required_environment"])
        self.assertIn("MICROSCORE_DATABASE_URL", readiness["missing_environment"])
        self.assertEqual(
            readiness["present_table_count"],
            readiness["required_table_count"],
        )
        self.assertGreaterEqual(readiness["json_column_count"], 1)
        self.assertGreaterEqual(readiness["tenant_scope_count"], 1)
        self.assertEqual(readiness["migration_artifact_count"], 1)
        self.assertEqual(readiness["latest_migration_version"], "0001_initial_schema")
        self.assertTrue(readiness["versioned_migration_contract_present"])
        self.assertTrue(readiness["disposable_migration_ci_present"])
        self.assertEqual(
            readiness["repository_adapter_contract_status"],
            "partial_method_groups",
        )
        self.assertTrue(readiness["repository_adapter_contract_present"])
        self.assertEqual(
            readiness["repository_adapter_contract_version"],
            "postgresql-repository-adapter-v6",
        )
        self.assertEqual(
            readiness["repository_adapter_module"],
            "microscore_api.postgres_repository",
        )
        self.assertEqual(
            readiness["repository_adapter_stage"],
            "model_registry_audit_organizations_identity_groups_v1",
        )
        self.assertEqual(readiness["repository_adapter_contract_method_count"], 52)
        self.assertEqual(readiness["repository_adapter_implemented_method_count"], 22)
        self.assertEqual(readiness["repository_adapter_pending_method_count"], 30)
        self.assertEqual(readiness["repository_adapter_read_only_method_count"], 10)
        self.assertEqual(readiness["repository_adapter_write_method_count"], 12)
        self.assertEqual(
            readiness["repository_adapter_completed_method_group_count"],
            4,
        )
        self.assertEqual(
            readiness["repository_adapter_completed_method_groups"],
            ["identity_access", "organizations", "model_registry", "audit"],
        )
        self.assertTrue(readiness["repository_adapter_model_registry_read_present"])
        self.assertTrue(readiness["repository_adapter_model_registry_write_present"])
        self.assertTrue(readiness["repository_adapter_model_registry_group_present"])
        self.assertTrue(readiness["repository_adapter_audit_group_present"])
        self.assertTrue(readiness["repository_adapter_organization_group_present"])
        self.assertTrue(readiness["repository_adapter_identity_access_group_present"])
        self.assertIn(
            "get_active_model_version",
            readiness["repository_adapter_implemented_methods"],
        )
        self.assertIn(
            "activate_model_version",
            readiness["repository_adapter_implemented_methods"],
        )
        self.assertIn(
            "record_audit_event",
            readiness["repository_adapter_implemented_methods"],
        )
        self.assertIn(
            "assign_user_organization",
            readiness["repository_adapter_implemented_methods"],
        )
        self.assertIn(
            "revoke_session_by_id",
            readiness["repository_adapter_implemented_methods"],
        )
        adapter_groups = {
            group["key"]: group
            for group in readiness["repository_adapter_contract_groups"]
        }
        self.assertIn("application_lifecycle", adapter_groups)
        self.assertIn(
            "create_application",
            adapter_groups["application_lifecycle"]["methods"],
        )
        self.assertEqual(
            adapter_groups["model_registry"]["implemented_method_count"],
            5,
        )
        self.assertEqual(adapter_groups["model_registry"]["pending_method_count"], 0)
        self.assertFalse(adapter_groups["model_registry"]["pending_methods"])
        self.assertEqual(adapter_groups["audit"]["implemented_method_count"], 2)
        self.assertEqual(adapter_groups["audit"]["pending_method_count"], 0)
        self.assertFalse(adapter_groups["audit"]["pending_methods"])
        self.assertEqual(adapter_groups["organizations"]["implemented_method_count"], 4)
        self.assertEqual(adapter_groups["organizations"]["pending_method_count"], 0)
        self.assertFalse(adapter_groups["organizations"]["pending_methods"])
        self.assertEqual(adapter_groups["identity_access"]["implemented_method_count"], 11)
        self.assertEqual(adapter_groups["identity_access"]["pending_method_count"], 0)
        self.assertFalse(adapter_groups["identity_access"]["pending_methods"])
        self.assertEqual(len(readiness["migration_artifacts"]), 1)
        artifact = readiness["migration_artifacts"][0]
        self.assertEqual(
            artifact["path"],
            "migrations/postgresql/0001_initial_schema.sql",
        )
        self.assertEqual(artifact["table_count"], len(REQUIRED_SCHEMA_TABLES))
        self.assertEqual(artifact["jsonb_column_count"], len(JSON_TEXT_COLUMNS))
        self.assertEqual(
            artifact["tenant_scope_index_count"],
            len(POSTGRESQL_TENANT_SCOPE_INDEXES),
        )
        self.assertIn("loan_applications", artifact["tables"])
        self.assertIn(
            "loan_applications.behavioral_signals_json",
            artifact["jsonb_columns"],
        )
        self.assertIn("idx_staff_invites_organization", artifact["tenant_scope_indexes"])
        inventory_by_table = {
            row["table"]: row for row in readiness["schema_inventory"]
        }
        self.assertIn("loan_applications", inventory_by_table)
        self.assertIn(
            "behavioral_signals_json",
            inventory_by_table["loan_applications"]["json_columns"],
        )
        self.assertIn(
            "organization_id",
            inventory_by_table["loan_applications"]["tenant_scope_columns"],
        )
        parity_keys = {row["key"]: row for row in readiness["parity_checks"]}
        self.assertEqual(parity_keys["postgresql_schema_inventory"]["status"], "pass")
        self.assertEqual(
            parity_keys["postgresql_versioned_migration_artifacts"]["status"],
            "pass",
        )
        self.assertEqual(parity_keys["postgresql_jsonb_mapping"]["status"], "pass")
        self.assertEqual(
            parity_keys["postgresql_disposable_migration_ci"]["status"],
            "pass",
        )
        self.assertEqual(
            parity_keys["postgresql_repository_adapter_contract"]["status"],
            "pass",
        )
        self.assertEqual(
            parity_keys["postgresql_model_registry_read_adapter"]["status"],
            "pass",
        )
        self.assertEqual(
            parity_keys["postgresql_model_registry_method_group_adapter"]["status"],
            "pass",
        )
        self.assertEqual(
            parity_keys["postgresql_audit_method_group_adapter"]["status"],
            "pass",
        )
        self.assertEqual(
            parity_keys["postgresql_organization_method_group_adapter"]["status"],
            "pass",
        )
        self.assertEqual(
            parity_keys["postgresql_identity_access_method_group_adapter"]["status"],
            "pass",
        )
        self.assertEqual(parity_keys["postgresql_repository_backend"]["status"], "blocker")
        self.assertEqual(parity_keys["postgresql_disposable_ci"]["status"], "blocker")
        blocker_keys = {row["key"] for row in readiness["blockers"]}
        self.assertIn("postgresql_repository_backend_not_implemented", blocker_keys)
        self.assertNotIn("postgresql_versioned_migrations_missing", blocker_keys)
        self.assertNotIn("postgresql_disposable_migration_ci_missing", blocker_keys)
        self.assertNotIn("postgresql_repository_adapter_contract_missing", blocker_keys)
        self.assertIn("postgresql_disposable_parity_ci_missing", blocker_keys)
        self.assertIn("postgresql_database_url_missing", blocker_keys)
        self.assertIn("schema and parity contract", readiness["limitation"])

    def test_postgresql_initial_migration_draft_covers_sqlite_contract(self) -> None:
        sql = (
            PROJECT_ROOT / "migrations" / "postgresql" / "0001_initial_schema.sql"
        ).read_text(encoding="utf-8")

        for table in REQUIRED_SCHEMA_TABLES:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        for column in JSON_TEXT_COLUMNS:
            _, column_name = column.split(".", 1)
            self.assertIn(f"{column_name} JSONB", sql)
        for index_name in POSTGRESQL_TENANT_SCOPE_INDEXES:
            self.assertIn(f"CREATE INDEX IF NOT EXISTS {index_name}", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS schema_migrations", sql)
        self.assertIn("0001_initial_schema", sql)
        self.assertIn("WHERE is_active IS TRUE", sql)

    def test_postgresql_disposable_migration_ci_is_tracked(self) -> None:
        self.assertTrue(self.repository.postgresql_disposable_migration_ci_present())

    def test_unsupported_storage_backend_is_reported_before_sqlite_startup(self) -> None:
        configured = os.environ.copy()
        configured["MICROSCORE_STORAGE_BACKEND"] = "postgresql"
        with patch.dict(os.environ, configured, clear=True):
            with self.assertRaises(UnsupportedStorageBackendError) as raised:
                MicroScoreRepository(Path(self.tempdir.name) / "postgresql.sqlite3")

        self.assertIn("PostgreSQL is tracked", str(raised.exception))

    def test_duplicate_user_is_reported_cleanly(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")

        with self.assertRaises(DuplicateUserError):
            self.repository.create_user("borrower@example.com", "password-hash", "borrower")

    def test_user_listing_excludes_password_hashes(self) -> None:
        self.repository.create_user("borrower@example.com", "borrower-hash", "borrower")
        self.repository.create_user("analyst@example.com", "analyst-hash", "mfi_analyst")

        users = self.repository.list_users()

        self.assertEqual(len(users), 2)
        self.assertTrue(all("password_hash" not in user for user in users))
        self.assertEqual(
            {user["email"] for user in users},
            {"borrower@example.com", "analyst@example.com"},
        )
        self.assertTrue(all("disabled_at" in user for user in users))
        self.assertTrue(all("mfa_attested_at" in user for user in users))

    def test_mfa_attestation_persists_for_staff_users(self) -> None:
        self.repository.create_user("admin@example.com", "admin-hash", "admin")
        self.repository.create_user("analyst@example.com", "analyst-hash", "mfi_analyst")

        attested = self.repository.attest_user_mfa(
            "analyst@example.com",
            "admin@example.com",
            "pilot_attestation",
        )

        self.assertEqual(attested["email"], "analyst@example.com")
        self.assertIsNotNone(attested["mfa_attested_at"])
        self.assertEqual(attested["mfa_attested_by"], "admin@example.com")
        self.assertEqual(attested["mfa_method"], "pilot_attestation")
        self.assertFalse(attested["was_already_attested"])
        self.assertEqual(
            self.repository.get_user("analyst@example.com")["mfa_method"],
            "pilot_attestation",
        )

        repeated = self.repository.attest_user_mfa(
            "analyst@example.com",
            "admin@example.com",
            "totp",
        )
        self.assertTrue(repeated["was_already_attested"])
        self.assertEqual(repeated["mfa_method"], "pilot_attestation")

    def test_disabled_user_sessions_are_revoked(self) -> None:
        self.repository.create_user("admin@example.com", "admin-hash", "admin")
        self.repository.create_user("analyst@example.com", "analyst-hash", "mfi_analyst")
        self.repository.create_session("analyst-token", "analyst@example.com")

        disabled = self.repository.disable_user("analyst@example.com", "admin@example.com")

        self.assertEqual(disabled["email"], "analyst@example.com")
        self.assertIsNotNone(disabled["disabled_at"])
        self.assertEqual(disabled["disabled_by"], "admin@example.com")
        self.assertEqual(disabled["revoked_session_count"], 1)
        self.assertFalse(disabled["was_already_disabled"])
        self.assertIsNone(self.repository.get_user_by_token("analyst-token"))

        repeated = self.repository.disable_user("analyst@example.com", "admin@example.com")
        self.assertTrue(repeated["was_already_disabled"])
        self.assertEqual(repeated["revoked_session_count"], 0)

        reactivated = self.repository.reactivate_user("analyst@example.com")
        self.assertEqual(reactivated["email"], "analyst@example.com")
        self.assertIsNone(reactivated["disabled_at"])
        self.assertIsNone(reactivated["disabled_by"])
        self.assertFalse(reactivated["was_already_active"])
        self.assertIsNotNone(reactivated["previous_disabled_at"])
        self.assertEqual(reactivated["previous_disabled_by"], "admin@example.com")

        repeated_reactivation = self.repository.reactivate_user("analyst@example.com")
        self.assertTrue(repeated_reactivation["was_already_active"])
        self.assertIsNone(repeated_reactivation["previous_disabled_at"])

    def test_staff_invites_persist_and_accept_once(self) -> None:
        self.repository.create_organization(
            organization_id="mfi-a",
            name="MFI A",
            region="Pavlodar region",
        )
        self.repository.create_user("admin@example.com", "admin-hash", "admin")
        created = self.repository.create_staff_invite(
            token="staff-invite-token",
            email="invited@example.com",
            role="mfi_analyst",
            organization_id="mfi-a",
            created_by="admin@example.com",
            expires_at="2026-06-26T00:00:00+00:00",
        )

        self.assertEqual(created["email"], "invited@example.com")
        self.assertIsNone(created["accepted_at"])
        self.assertIsNone(created["revoked_at"])
        self.assertIsNone(created["delivered_at"])
        self.assertEqual(created["delivery_attempt_count"], 0)
        self.assertEqual(self.repository.get_staff_invite("staff-invite-token")["role"], "mfi_analyst")
        self.assertEqual(len(self.repository.list_staff_invites()), 1)
        attempt = self.repository.record_staff_invite_delivery_attempt(
            attempt_id="attempt-1",
            token="staff-invite-token",
            attempted_by="admin@example.com",
            provider="local_outbox",
            status="sent",
            channel="email",
            recipient="invited@example.com",
            url_base="http://127.0.0.1:5173",
            note="queued from local outbox",
        )
        self.assertEqual(attempt["provider"], "local_outbox")
        self.assertEqual(attempt["status"], "sent")
        self.assertEqual(attempt["invite_token"], "staff-invite-token")
        self.assertEqual(attempt["worker_status"], "completed")
        self.assertEqual(attempt["worker_attempt_count"], 0)
        self.assertIsNone(attempt["next_worker_run_at"])
        attempts = self.repository.list_staff_invite_delivery_attempts("staff-invite-token")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["attempt_id"], "attempt-1")
        invite_with_attempt = self.repository.get_staff_invite("staff-invite-token")
        self.assertEqual(invite_with_attempt["delivery_attempt_count"], 1)
        self.assertEqual(invite_with_attempt["last_delivery_status"], "sent")
        self.assertEqual(invite_with_attempt["last_delivery_provider"], "local_outbox")
        event = self.repository.record_staff_invite_delivery_event(
            event_id="event-1",
            provider="local_outbox",
            provider_event_id="provider-event-1",
            attempt_id="attempt-1",
            token="staff-invite-token",
            event_type="delivered",
            mapped_attempt_status="sent",
            occurred_at="2026-06-25T12:00:00+00:00",
            recipient="invited@example.com",
            error=None,
            metadata={"message_id": "demo-message-1"},
        )
        self.assertEqual(event["event_type"], "delivered")
        self.assertFalse(event["was_duplicate"])
        duplicate_event = self.repository.record_staff_invite_delivery_event(
            event_id="event-duplicate",
            provider="local_outbox",
            provider_event_id="provider-event-1",
            attempt_id="attempt-1",
            token="staff-invite-token",
            event_type="delivered",
            mapped_attempt_status="sent",
            occurred_at=None,
            recipient=None,
            error=None,
            metadata={},
        )
        self.assertEqual(duplicate_event["event_id"], "event-1")
        self.assertTrue(duplicate_event["was_duplicate"])
        self.assertEqual(
            len(self.repository.list_staff_invite_delivery_events("staff-invite-token")),
            1,
        )
        invite_with_event = self.repository.get_staff_invite("staff-invite-token")
        self.assertEqual(invite_with_event["delivery_event_count"], 1)
        self.assertEqual(invite_with_event["last_delivery_event_type"], "delivered")
        updated_attempt = self.repository.update_staff_invite_delivery_attempt_status(
            "attempt-1",
            status="failed",
            error="provider bounce",
        )
        self.assertEqual(updated_attempt["status"], "failed")
        self.assertEqual(updated_attempt["error"], "provider bounce")
        self.assertEqual(updated_attempt["worker_status"], "completed")
        queued_attempt = self.repository.record_staff_invite_delivery_attempt(
            attempt_id="attempt-queued",
            token="staff-invite-token",
            attempted_by="admin@example.com",
            provider="transactional_email",
            status="queued",
            channel="email",
            recipient="invited@example.com",
            url_base="http://127.0.0.1:5173",
            note="queued for worker",
        )
        self.assertEqual(queued_attempt["worker_status"], "queued")
        self.assertEqual(queued_attempt["worker_attempt_count"], 0)
        self.assertIsNotNone(queued_attempt["next_worker_run_at"])
        outbox_attempts = self.repository.list_staff_invite_delivery_outbox_attempts()
        self.assertIn(
            "attempt-queued",
            {outbox_attempt["attempt_id"] for outbox_attempt in outbox_attempts},
        )
        worker_retry = self.repository.update_staff_invite_delivery_worker_state(
            "attempt-queued",
            status="queued",
            error="transient provider unavailable",
            worker_status="retry_scheduled",
            worker_attempt_count=1,
            next_worker_run_at="2026-06-25T12:05:00+00:00",
            dead_letter_at=None,
            last_worker_error="transient provider unavailable",
        )
        self.assertEqual(worker_retry["worker_status"], "retry_scheduled")
        self.assertEqual(worker_retry["worker_attempt_count"], 1)
        self.assertEqual(worker_retry["next_worker_run_at"], "2026-06-25T12:05:00+00:00")
        worker_dead_letter = self.repository.update_staff_invite_delivery_worker_state(
            "attempt-queued",
            status="failed",
            error="exhausted provider retries",
            worker_status="dead_letter",
            worker_attempt_count=2,
            next_worker_run_at=None,
            dead_letter_at="2026-06-25T12:10:00+00:00",
            last_worker_error="exhausted provider retries",
        )
        self.assertEqual(worker_dead_letter["status"], "failed")
        self.assertEqual(worker_dead_letter["worker_status"], "dead_letter")
        self.assertEqual(worker_dead_letter["dead_letter_at"], "2026-06-25T12:10:00+00:00")
        delivered = self.repository.mark_staff_invite_delivered(
            "staff-invite-token",
            delivered_by="admin@example.com",
            channel="manual_copy",
            recipient="invited@example.com",
            url_base="http://127.0.0.1:5173",
            note="copied during local onboarding",
        )
        self.assertEqual(delivered["delivered_by"], "admin@example.com")
        self.assertEqual(delivered["delivery_channel"], "manual_copy")
        self.assertEqual(delivered["delivery_recipient"], "invited@example.com")
        self.assertFalse(delivered["was_already_delivered"])
        repeated_delivery = self.repository.mark_staff_invite_delivered(
            "staff-invite-token",
            delivered_by="admin@example.com",
            channel="email",
            recipient="changed@example.com",
            url_base="https://example.org",
            note=None,
        )
        self.assertTrue(repeated_delivery["was_already_delivered"])
        self.assertEqual(repeated_delivery["delivery_channel"], "manual_copy")
        self.repository.create_user(
            "invited@example.com",
            "analyst-hash",
            "mfi_analyst",
            "mfi-a",
        )
        self.assertTrue(
            self.repository.mark_staff_invite_accepted(
                "staff-invite-token",
                "invited@example.com",
            )
        )
        self.assertFalse(
            self.repository.mark_staff_invite_accepted(
                "staff-invite-token",
                "invited@example.com",
            )
        )

        reopened = MicroScoreRepository(self.db_path)
        accepted = reopened.get_staff_invite("staff-invite-token")
        self.assertEqual(accepted["accepted_by"], "invited@example.com")
        self.assertIsNotNone(accepted["accepted_at"])
        self.assertIsNotNone(accepted["delivered_at"])
        self.assertEqual(accepted["delivery_url_base"], "http://127.0.0.1:5173")
        self.assertFalse(
            reopened.mark_staff_invite_revoked(
                "staff-invite-token",
                "admin@example.com",
            )
        )

        revoked_created = reopened.create_staff_invite(
            token="revoked-staff-invite-token",
            email="revoked@example.com",
            role="mfi_analyst",
            organization_id="mfi-a",
            created_by="admin@example.com",
            expires_at="2026-06-26T00:00:00+00:00",
        )
        self.assertIsNone(revoked_created["revoked_at"])
        self.assertTrue(
            reopened.mark_staff_invite_revoked(
                "revoked-staff-invite-token",
                "admin@example.com",
            )
        )
        self.assertFalse(
            reopened.mark_staff_invite_revoked(
                "revoked-staff-invite-token",
                "admin@example.com",
            )
        )
        self.assertFalse(
            reopened.mark_staff_invite_accepted(
                "revoked-staff-invite-token",
                "revoked@example.com",
            )
        )
        revoked = MicroScoreRepository(self.db_path).get_staff_invite("revoked-staff-invite-token")
        self.assertEqual(revoked["revoked_by"], "admin@example.com")
        self.assertIsNotNone(revoked["revoked_at"])

    def test_organization_membership_scopes_application_listing(self) -> None:
        for organization_id, name in (("mfi-a", "MFI A"), ("mfi-b", "MFI B")):
            self.repository.create_organization(
                organization_id=organization_id,
                name=name,
                region="Pavlodar region",
            )
        self.repository.create_user("borrower@example.com", "hash", "borrower")
        self.repository.create_user(
            "analyst-a@example.com",
            "hash",
            "mfi_analyst",
            "mfi-a",
        )

        for organization_id in ("mfi-a", "mfi-b"):
            self.repository.create_application(
                application_id=f"app-{organization_id}",
                borrower_email="borrower@example.com",
                requested_amount=250_000,
                purpose="inventory",
                district="Pavlodar city",
                settlement_type="urban",
                behavioral_signals={"loan_application_amount": 250_000},
                organization_id=organization_id,
            )

        self.assertEqual(len(self.repository.list_organizations()), 2)
        self.assertEqual(
            self.repository.get_user("analyst-a@example.com")["organization_id"],
            "mfi-a",
        )
        self.assertEqual(
            [item["id"] for item in self.repository.list_applications("mfi-a")],
            ["app-mfi-a"],
        )
        self.assertEqual(
            [item["id"] for item in self.repository.list_applications("mfi-b")],
            ["app-mfi-b"],
        )

    def test_sessions_expire_and_can_be_revoked(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
        now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

        session = self.repository.create_session(
            "active-token",
            "borrower@example.com",
            created_at=(now - timedelta(hours=1)).isoformat(),
        )
        self.assertEqual(session["session_ttl_seconds"], 8 * 60 * 60)
        self.assertIn("session_expires_at", session)
        active_user = self.repository.get_user_by_token(
            "active-token",
            now=now,
            ttl_hours=8,
        )
        self.assertIsNotNone(active_user)
        self.assertEqual(active_user["session_ttl_seconds"], 8 * 60 * 60)
        self.assertIn("session_expires_at", active_user)
        self.assertTrue(self.repository.revoke_session("active-token"))
        self.assertIsNone(
            self.repository.get_user_by_token(
                "active-token",
                now=now,
                ttl_hours=8,
            )
        )

        self.repository.create_session(
            "expired-token",
            "borrower@example.com",
            created_at=(now - timedelta(hours=9)).isoformat(),
        )
        self.assertIsNone(
            self.repository.get_user_by_token(
                "expired-token",
                now=now,
                ttl_hours=8,
            )
        )
        self.assertFalse(self.repository.revoke_session("expired-token"))

    def test_active_staff_sessions_hide_tokens_and_revoke_by_hash(self) -> None:
        self.repository.create_organization(
            organization_id="pavlodar-mfi-a",
            name="Pavlodar MFI A",
            region="Pavlodar region",
        )
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
        self.repository.create_user("admin@example.com", "password-hash", "admin")
        self.repository.create_user(
            "analyst@example.com",
            "password-hash",
            "mfi_analyst",
            "pavlodar-mfi-a",
        )
        now = datetime.now(timezone.utc)
        self.repository.create_session(
            "borrower-token",
            "borrower@example.com",
            created_at=(now - timedelta(hours=1)).isoformat(),
        )
        self.repository.create_session(
            "admin-token",
            "admin@example.com",
            created_at=(now - timedelta(hours=1)).isoformat(),
        )
        self.repository.create_session(
            "analyst-token",
            "analyst@example.com",
            created_at=(now - timedelta(hours=1)).isoformat(),
        )
        self.repository.create_session(
            "expired-analyst-token",
            "analyst@example.com",
            created_at=(now - timedelta(hours=9)).isoformat(),
        )

        sessions = self.repository.list_active_sessions(
            staff_only=True,
            now=now,
            ttl_hours=8,
        )
        self.assertEqual({session["email"] for session in sessions}, {"admin@example.com", "analyst@example.com"})
        self.assertTrue(all(session["role"] in {"admin", "mfi_analyst"} for session in sessions))
        self.assertIn("token", sessions[0])
        analyst_session_id = hashlib.sha256("analyst-token".encode("utf-8")).hexdigest()
        self.assertTrue(any(session["session_id"] == analyst_session_id for session in sessions))

        revoked = self.repository.revoke_session_by_id(analyst_session_id, staff_only=True)
        self.assertIsNotNone(revoked)
        self.assertEqual(revoked["email"], "analyst@example.com")
        self.assertFalse(self.repository.revoke_session_by_id(analyst_session_id, staff_only=True))
        self.assertIsNone(self.repository.get_user_by_token("analyst-token", now=now, ttl_hours=8))

    def test_model_registry_has_active_default_and_atomic_activation(self) -> None:
        default_model = self.repository.get_active_model_version()
        self.assertEqual(default_model["version"], "research-v0.1")
        self.assertTrue(default_model["is_active"])
        self.assertEqual(default_model["random_state"], 42)
        self.assertTrue(default_model["limitations"])

        candidate = self.repository.create_model_version(
            version="research-v0.2",
            model_name="Logistic Regression",
            feature_schema_version="behavioral-v2",
            training_data_label="synthetic-credit-risk-v2",
            random_state=77,
            metrics={"roc_auc": 0.82, "brier_score": 0.18},
            limitations=["Synthetic validation only."],
            created_by="admin@example.com",
        )
        self.assertEqual(candidate["lifecycle_status"], "candidate")
        self.assertFalse(candidate["is_active"])

        connection = sqlite3.connect(self.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE model_versions SET is_active = 1 WHERE version = ?",
                    ("research-v0.2",),
                )
                connection.commit()
            connection.rollback()
        finally:
            connection.close()

        activated = self.repository.activate_model_version("research-v0.2")
        self.assertTrue(activated["is_active"])
        self.assertEqual(activated["lifecycle_status"], "active")
        self.assertEqual(
            self.repository.get_model_version("research-v0.1")["lifecycle_status"],
            "inactive",
        )
        self.assertEqual(
            self.repository.get_active_model_version()["version"],
            "research-v0.2",
        )
        self.assertIsNone(self.repository.activate_model_version("missing-version"))

        reopened = MicroScoreRepository(self.db_path)
        self.assertEqual(reopened.get_active_model_version()["version"], "research-v0.2")
        self.assertEqual(len(reopened.list_model_versions()), 2)

        with self.assertRaises(DuplicateModelVersionError):
            reopened.create_model_version(
                version="research-v0.2",
                model_name="Logistic Regression",
                feature_schema_version="behavioral-v2",
                training_data_label="synthetic-credit-risk-v2",
                random_state=77,
                metrics={},
                limitations=["Synthetic validation only."],
                created_by="admin@example.com",
            )

    def test_portfolio_simulation_registry_persists_and_scopes_runs(self) -> None:
        self.repository.create_organization(
            organization_id="mfi-a",
            name="MFI A",
            region="Pavlodar region",
        )
        self.repository.create_organization(
            organization_id="mfi-b",
            name="MFI B",
            region="Pavlodar region",
        )
        self.repository.create_user(
            "analyst@example.com",
            "hash",
            "mfi_analyst",
            "mfi-a",
        )
        result = {
            "simulation_id": "sim-a",
            "generated_at": "2026-06-19T12:00:00+00:00",
            "organization_id": "mfi-a",
            "actor_email": "analyst@example.com",
            "portfolio_fingerprint": "a" * 64,
            "assumptions": {"iterations": 500, "seed": 7},
            "policy": {"name": "balanced_review"},
            "scenarios": [],
            "warnings": [],
        }
        created = self.repository.create_portfolio_simulation(
            simulation_id="sim-a",
            organization_id="mfi-a",
            actor_email="analyst@example.com",
            portfolio_fingerprint="a" * 64,
            request_payload={"iterations": 500, "seed": 7},
            result_payload=result,
            created_at=result["generated_at"],
        )

        self.assertEqual(created["id"], "sim-a")
        self.assertEqual(created["request"]["seed"], 7)
        self.assertEqual(created["result"]["portfolio_fingerprint"], "a" * 64)
        self.assertEqual(len(self.repository.list_portfolio_simulations("mfi-a")), 1)
        self.assertEqual(self.repository.list_portfolio_simulations("mfi-b"), [])

        reopened = MicroScoreRepository(self.db_path)
        self.assertEqual(
            reopened.get_portfolio_simulation("sim-a")["actor_email"],
            "analyst@example.com",
        )

    def test_score_results_segment_analytics_and_audit_events(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
        self.repository.create_user("analyst@example.com", "password-hash", "mfi_analyst")
        self.repository.create_application(
            application_id="app-1",
            borrower_email="borrower@example.com",
            requested_amount=300_000,
            purpose="inventory",
            district="Bayanaul",
            settlement_type="rural",
            behavioral_signals={
                "gender": "Male",
                "employment_status": "Employed",
                "loan_application_amount": 300_000,
            },
        )

        updated = self.repository.update_application_score(
            application_id="app-1",
            actor_email="analyst@example.com",
            score_result={
                "model_name": "Logistic Regression",
                "model_version": "research-v0.1",
                "high_risk_probability": 0.72,
                "risk_band": "high",
                "warnings": [],
            },
        )

        analytics = self.repository.segment_analytics()
        audit_events = self.repository.list_audit_events()

        self.assertEqual(updated["status"], "scored")
        self.assertTrue(
            any(row["segment_feature"] == "settlement_type" and row["segment_value"] == "rural" for row in analytics)
        )
        self.assertTrue(any(event["action"] == "application_scored" for event in audit_events))

    def test_application_decision_persists_and_records_audit_event(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
        self.repository.create_user("analyst@example.com", "password-hash", "mfi_analyst")
        self.repository.create_application(
            application_id="app-1",
            borrower_email="borrower@example.com",
            requested_amount=300_000,
            purpose="inventory",
            district="Bayanaul",
            settlement_type="rural",
            behavioral_signals={"loan_application_amount": 300_000},
        )
        self.repository.update_application_score(
            application_id="app-1",
            actor_email="analyst@example.com",
            score_result={
                "model_name": "Logistic Regression",
                "model_version": "research-v0.1",
                "high_risk_probability": 0.42,
                "risk_band": "medium",
                "proxy_sensitivity_delta": 0.24,
                "decision_support": {
                    "recommendation_code": "manual_review_proxy_sensitive",
                    "title": "Manual review - proxy-sensitive score",
                    "rationale": [],
                    "next_steps": [],
                },
                "warnings": [
                    "Risk estimate is sensitive to late_payment_count; review the thin-file scenario before deciding.",
                ],
            },
        )

        updated = self.repository.record_application_decision(
            application_id="app-1",
            actor_email="analyst@example.com",
            decision="review",
            policy_name="balanced_review",
            note="Request income stability evidence.",
        )
        reopened = MicroScoreRepository(self.db_path)
        application = reopened.get_application("app-1")
        audit_events = reopened.list_audit_events()

        self.assertEqual(updated["decision_result"]["decision"], "review")
        self.assertEqual(application["decision_result"]["policy_name"], "balanced_review")
        self.assertEqual(application["decision_result"]["actor_email"], "analyst@example.com")
        self.assertTrue(
            any(event["action"] == "application_decision_recorded" for event in audit_events)
        )

        analytics = reopened.decision_analytics()
        timeline = reopened.list_application_timeline("app-1")

        self.assertEqual(analytics["application_count"], 1)
        self.assertEqual(analytics["decided_application_count"], 1)
        self.assertTrue(
            any(row["decision"] == "review" and row["count"] == 1 for row in analytics["decision_rows"])
        )
        self.assertTrue(
            any(row["policy_name"] == "balanced_review" for row in analytics["policy_rows"])
        )
        self.assertTrue(
            any(
                row["risk_band"] == "medium" and row["decision"] == "review"
                for row in analytics["risk_rows"]
            )
        )
        self.assertTrue(
            any(
                row["district"] == "Bayanaul" and row["decision"] == "review"
                for row in analytics["district_rows"]
            )
        )
        self.assertTrue(
            any(
                row["recommendation_code"] == "manual_review_proxy_sensitive"
                for row in analytics["recommendation_rows"]
            )
        )
        self.assertTrue(
            any(
                row["proxy_sensitivity_bucket"] == "proxy_sensitive"
                for row in analytics["proxy_rows"]
            )
        )
        self.assertEqual(
            [event["action"] for event in timeline],
            [
                "application_created",
                "application_scored",
                "application_decision_recorded",
            ],
        )

    def test_application_lifecycle_transitions_are_strict(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
        self.repository.create_user("analyst@example.com", "password-hash", "mfi_analyst")
        self.repository.create_application(
            application_id="lifecycle-app",
            borrower_email="borrower@example.com",
            requested_amount=120_000,
            purpose="equipment",
            district="Aksu",
            settlement_type="industrial_city",
            behavioral_signals={"loan_application_amount": 120_000},
        )
        first_score = {
            "model_name": "Logistic Regression",
            "model_version": "research-v0.1",
            "high_risk_probability": 0.31,
            "risk_band": "low",
            "warnings": [],
        }
        scored = self.repository.update_application_score(
            application_id="lifecycle-app",
            actor_email="analyst@example.com",
            score_result=first_score,
        )
        self.assertEqual(scored["status"], "scored")

        reviewed = self.repository.record_application_decision(
            application_id="lifecycle-app",
            actor_email="analyst@example.com",
            decision="review",
            policy_name="balanced_review",
            note="Verify seasonal income.",
        )
        self.assertEqual(reviewed["status"], "under_review")

        rescored = self.repository.update_application_score(
            application_id="lifecycle-app",
            actor_email="analyst@example.com",
            score_result={**first_score, "model_version": "research-v0.2"},
        )
        self.assertEqual(rescored["status"], "under_review")

        with self.assertRaises(InvalidApplicationTransitionError):
            self.repository.record_application_decision(
                application_id="lifecycle-app",
                actor_email="analyst@example.com",
                decision="review",
                policy_name="balanced_review",
                note="Duplicate review.",
            )

        approved = self.repository.record_application_decision(
            application_id="lifecycle-app",
            actor_email="analyst@example.com",
            decision="approve",
            policy_name="balanced_review",
            note="Affordability evidence verified.",
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(
            [row["decision"] for row in self.repository.list_application_decisions("lifecycle-app")],
            ["review", "approve"],
        )

        with self.assertRaises(InvalidApplicationTransitionError):
            self.repository.update_application_score(
                application_id="lifecycle-app",
                actor_email="analyst@example.com",
                score_result=first_score,
            )
        with self.assertRaises(InvalidApplicationTransitionError):
            self.repository.record_application_decision(
                application_id="lifecycle-app",
                actor_email="analyst@example.com",
                decision="decline",
                policy_name="balanced_review",
                note="Attempted reversal.",
            )

        self.assertEqual(
            [event["action"] for event in self.repository.list_application_timeline("lifecycle-app")],
            [
                "application_created",
                "application_scored",
                "application_decision_recorded",
                "application_rescored",
                "application_decision_recorded",
            ],
        )

    def test_clear_applications_keeps_users_and_records_audit_event(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
        self.repository.create_user("analyst@example.com", "password-hash", "mfi_analyst")
        self.repository.create_user("admin@example.com", "password-hash", "admin")
        self.repository.create_application(
            application_id="app-1",
            borrower_email="borrower@example.com",
            requested_amount=300_000,
            purpose="inventory",
            district="Bayanaul",
            settlement_type="rural",
            behavioral_signals={"loan_application_amount": 300_000},
        )
        self.repository.update_application_score(
            application_id="app-1",
            actor_email="analyst@example.com",
            score_result={
                "model_name": "Logistic Regression",
                "model_version": "research-v0.1",
                "high_risk_probability": 0.42,
                "risk_band": "medium",
                "warnings": [],
            },
        )
        self.repository.record_application_decision(
            application_id="app-1",
            actor_email="analyst@example.com",
            decision="review",
            policy_name="balanced_review",
            note="Request income stability evidence.",
        )

        deleted_count = self.repository.clear_applications(actor_email="admin@example.com")
        audit_events = self.repository.list_audit_events()
        analytics = self.repository.decision_analytics()

        self.assertEqual(deleted_count, 1)
        self.assertEqual(self.repository.list_applications(), [])
        self.assertEqual(analytics["application_count"], 0)
        self.assertEqual(analytics["decided_application_count"], 0)
        self.assertIsNotNone(self.repository.get_user("borrower@example.com"))
        self.assertTrue(any(event["action"] == "applications_cleared" for event in audit_events))


if __name__ == "__main__":
    unittest.main()
