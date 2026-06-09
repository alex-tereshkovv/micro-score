from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import DuplicateUserError, MicroScoreRepository


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

    def test_duplicate_user_is_reported_cleanly(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")

        with self.assertRaises(DuplicateUserError):
            self.repository.create_user("borrower@example.com", "password-hash", "borrower")

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

    def test_clear_applications_keeps_users_and_records_audit_event(self) -> None:
        self.repository.create_user("borrower@example.com", "password-hash", "borrower")
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

        deleted_count = self.repository.clear_applications(actor_email="admin@example.com")
        audit_events = self.repository.list_audit_events()

        self.assertEqual(deleted_count, 1)
        self.assertEqual(self.repository.list_applications(), [])
        self.assertIsNotNone(self.repository.get_user("borrower@example.com"))
        self.assertTrue(any(event["action"] == "applications_cleared" for event in audit_events))


if __name__ == "__main__":
    unittest.main()
