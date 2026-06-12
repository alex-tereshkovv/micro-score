from __future__ import annotations

import sys
import tempfile
import unittest
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - depends on optional app extra
    TestClient = None

if TestClient is not None:
    from microscore_api.database import MicroScoreRepository
    from microscore_api.main import app, get_repository


@unittest.skipIf(TestClient is None, "FastAPI app dependencies are not installed")
class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = MicroScoreRepository(Path(self.tempdir.name) / "api-test.sqlite3")
        app.dependency_overrides[get_repository] = lambda: self.repository
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.tempdir.cleanup()

    def _register(self, email: str, role: str) -> str:
        response = self.client.post(
            "/auth/register",
            json={"email": email, "password": "password123", "role": role},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_full_borrower_mfi_admin_flow(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertIn("api-test.sqlite3", health.json()["database"])

        borrower_token = self._register("borrower@example.com", "borrower")
        application_response = self.client.post(
            "/applications",
            headers=self._headers(borrower_token),
            json={
                "requested_amount": 300_000,
                "purpose": "working capital",
                "district": "Pavlodar city",
                "settlement_type": "urban",
                "behavioral_signals": {
                    "annual_income": 4_200_000,
                    "total_outstanding_debt": 650_000,
                    "mobile_banking_logins": 18,
                    "online_transfer_frequency": 7,
                    "atm_withdrawal_frequency": 2,
                    "avg_deposit_amount": 140_000,
                    "debit_card_spending": 90_000,
                    "num_open_loans": 1,
                    "late_payment_count": 0,
                    "gender": "Female",
                    "employment_status": "Self-employed",
                },
            },
        )
        self.assertEqual(application_response.status_code, 200, application_response.text)
        application_id = application_response.json()["id"]

        analyst_token = self._register("analyst@example.com", "mfi_analyst")
        list_response = self.client.get(
            "/mfi/applications",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(len(list_response.json()), 1)

        score_response = self.client.post(
            f"/mfi/applications/{application_id}/score",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(score_response.status_code, 200, score_response.text)
        scored_application = score_response.json()
        self.assertEqual(scored_application["status"], "scored")
        self.assertIn(scored_application["score_result"]["risk_band"], {"low", "medium", "high"})

        decision_response = self.client.post(
            f"/mfi/applications/{application_id}/decision",
            headers=self._headers(analyst_token),
            json={
                "decision": "review",
                "policy_name": "balanced_review",
                "note": "Request income stability evidence.",
            },
        )
        self.assertEqual(decision_response.status_code, 200, decision_response.text)
        decision_payload = decision_response.json()["decision_result"]
        self.assertEqual(decision_payload["decision"], "review")
        self.assertEqual(decision_payload["policy_name"], "balanced_review")

        timeline_response = self.client.get(
            f"/applications/{application_id}/timeline",
            headers=self._headers(borrower_token),
        )
        self.assertEqual(timeline_response.status_code, 200, timeline_response.text)
        timeline = timeline_response.json()
        self.assertEqual(
            [event["action"] for event in timeline],
            [
                "application_created",
                "application_scored",
                "application_decision_recorded",
            ],
        )
        self.assertTrue(all(event["title"] for event in timeline))

        review_packet_response = self.client.get(
            f"/mfi/applications/{application_id}/review-packet",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(review_packet_response.status_code, 200, review_packet_response.text)
        review_packet = review_packet_response.json()
        self.assertEqual(review_packet["application_id"], application_id)
        self.assertEqual(review_packet["application"]["borrower_email"], "borrower@example.com")
        self.assertEqual(review_packet["analyst_decision"]["decision"], "review")
        self.assertEqual(len(review_packet["timeline_events"]), 3)
        self.assertTrue(review_packet["checklist"])
        self.assertIn("audit_note", review_packet)

        analytics_response = self.client.get(
            "/mfi/analytics/segments",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(analytics_response.status_code, 200, analytics_response.text)
        self.assertTrue(
            any(row["segment_feature"] == "gender" for row in analytics_response.json())
        )

        policy_response = self.client.get(
            "/mfi/analytics/policies",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(policy_response.status_code, 200, policy_response.text)
        policy_payload = policy_response.json()
        self.assertEqual(policy_payload["scored_application_count"], 1)
        self.assertTrue(
            any(row["policy"] == "balanced_review" for row in policy_payload["policies"])
        )
        self.assertTrue(
            any(row["segment_feature"] == "gender" for row in policy_payload["segments"])
        )

        decision_analytics_response = self.client.get(
            "/mfi/analytics/decisions",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(
            decision_analytics_response.status_code,
            200,
            decision_analytics_response.text,
        )
        decision_analytics = decision_analytics_response.json()
        self.assertEqual(decision_analytics["decided_application_count"], 1)
        self.assertTrue(
            any(row["decision"] == "review" for row in decision_analytics["decision_rows"])
        )
        self.assertTrue(decision_analytics["risk_rows"])
        self.assertTrue(decision_analytics["district_rows"])
        self.assertTrue(decision_analytics["recommendation_rows"])
        self.assertTrue(decision_analytics["proxy_rows"])

        export_response = self.client.get(
            "/mfi/applications/export.csv",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(export_response.status_code, 200, export_response.text)
        self.assertIn("text/csv", export_response.headers["content-type"])
        self.assertIn("microscore-applications.csv", export_response.headers["content-disposition"])
        csv_text = export_response.text
        self.assertIn("application_id,borrower_email,status", csv_text)
        self.assertIn(application_id, csv_text)
        self.assertIn("borrower@example.com", csv_text)
        self.assertIn("balanced_review", csv_text)

        admin_token = self._register("admin@example.com", "admin")
        audit_response = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        )
        self.assertEqual(audit_response.status_code, 200, audit_response.text)
        self.assertTrue(
            any(event["action"] == "application_scored" for event in audit_response.json())
        )
        self.assertTrue(
            any(event["action"] == "application_decision_recorded" for event in audit_response.json())
        )

    def test_openapi_exposes_product_response_schemas(self) -> None:
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200, response.text)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("ApplicationDecisionCreate", schemas)
        self.assertIn("ApplicationDecisionResponse", schemas)
        self.assertIn("ApplicationTimelineEventResponse", schemas)
        self.assertIn("ApplicationReviewPacketResponse", schemas)
        self.assertIn("ReviewPacketApplicationSummary", schemas)
        self.assertIn("ReviewPacketModelSummary", schemas)
        self.assertIn("ReviewChecklistItem", schemas)
        self.assertIn("DecisionAnalyticsResponse", schemas)
        self.assertIn("DecisionAnalyticsRow", schemas)
        self.assertIn("DecisionPolicyAnalyticsRow", schemas)
        self.assertIn("DecisionRiskAnalyticsRow", schemas)
        self.assertIn("DecisionDistrictAnalyticsRow", schemas)
        self.assertIn("DecisionRecommendationAnalyticsRow", schemas)
        self.assertIn("DecisionProxyAnalyticsRow", schemas)
        self.assertIn("LoanApplicationResponse", schemas)
        self.assertIn("ScoreResultResponse", schemas)
        self.assertIn("LocalExplanationResponse", schemas)
        self.assertIn("ScenarioScoreResponse", schemas)
        self.assertIn("DecisionSupportResponse", schemas)
        self.assertIn("SegmentAnalyticsRow", schemas)
        self.assertIn("PolicyAnalyticsResponse", schemas)
        self.assertIn("PolicyAnalyticsRow", schemas)
        self.assertIn("SegmentPolicyAnalyticsRow", schemas)
        self.assertIn("AuditEventResponse", schemas)
        self.assertIn("ClearApplicationsResponse", schemas)

    def test_cors_headers_allow_local_frontend(self) -> None:
        response = self.client.get(
            "/health",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")

    def test_admin_can_clear_applications(self) -> None:
        borrower_token = self._register("borrower@example.com", "borrower")
        application_response = self.client.post(
            "/applications",
            headers=self._headers(borrower_token),
            json={
                "requested_amount": 300_000,
                "purpose": "working capital",
                "district": "Pavlodar city",
                "settlement_type": "urban",
                "behavioral_signals": {"loan_application_amount": 300_000},
            },
        )
        self.assertEqual(application_response.status_code, 200, application_response.text)

        admin_token = self._register("admin@example.com", "admin")
        clear_response = self.client.delete(
            "/admin/applications",
            headers=self._headers(admin_token),
        )
        list_response = self.client.get(
            "/mfi/applications",
            headers=self._headers(admin_token),
        )

        self.assertEqual(clear_response.status_code, 200, clear_response.text)
        self.assertEqual(clear_response.json()["deleted_count"], 1)
        self.assertEqual(list_response.json(), [])


if __name__ == "__main__":
    unittest.main()
