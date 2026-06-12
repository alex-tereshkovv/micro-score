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
