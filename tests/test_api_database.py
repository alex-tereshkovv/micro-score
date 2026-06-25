from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import (
    DuplicateModelVersionError,
    DuplicateUserError,
    InvalidApplicationTransitionError,
    MicroScoreRepository,
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
        self.assertEqual(self.repository.get_staff_invite("staff-invite-token")["role"], "mfi_analyst")
        self.assertEqual(len(self.repository.list_staff_invites()), 1)
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
