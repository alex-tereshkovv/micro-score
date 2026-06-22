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
    from microscore_api.main import app, get_login_rate_limiter, get_repository
    from microscore_api.rate_limit import LoginRateLimiter
    from microscore_api.security import hash_password


TEST_PASSWORD = "StrongPassword1!"
TEST_ORGANIZATION_ID = "pavlodar-mfi-a"
SECOND_ORGANIZATION_ID = "pavlodar-mfi-b"


@unittest.skipIf(TestClient is None, "FastAPI app dependencies are not installed")
class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = MicroScoreRepository(Path(self.tempdir.name) / "api-test.sqlite3")
        self.repository.create_organization(
            organization_id=TEST_ORGANIZATION_ID,
            name="Pavlodar MFI A",
            region="Pavlodar region",
        )
        self.repository.create_organization(
            organization_id=SECOND_ORGANIZATION_ID,
            name="Pavlodar MFI B",
            region="Pavlodar region",
        )
        self.login_limiter = LoginRateLimiter(
            max_attempts=3,
            window_seconds=60,
            block_seconds=120,
        )
        app.dependency_overrides[get_repository] = lambda: self.repository
        app.dependency_overrides[get_login_rate_limiter] = lambda: self.login_limiter
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.tempdir.cleanup()

    def _register(self, email: str, role: str) -> str:
        if role == "borrower":
            response = self.client.post(
                "/auth/register",
                json={"email": email, "password": TEST_PASSWORD, "role": role},
            )
        else:
            self.repository.create_user(
                email,
                hash_password(TEST_PASSWORD),
                role,
                TEST_ORGANIZATION_ID if role == "mfi_analyst" else None,
            )
            response = self.client.post(
                "/auth/login",
                json={"email": email, "password": TEST_PASSWORD},
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
                "organization_id": TEST_ORGANIZATION_ID,
                "consent_confirmed": True,
                "consent_version": "synthetic-demo-v1",
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
        borrower_application = application_response.json()
        application_id = borrower_application["id"]
        self.assertEqual(borrower_application["status"], "submitted")
        self.assertFalse(borrower_application["terminal"])
        self.assertIn("waiting for MFI scoring", borrower_application["status_message"])
        self.assertNotIn("borrower_email", borrower_application)
        self.assertNotIn("behavioral_signals", borrower_application)
        self.assertNotIn("score_result", borrower_application)

        borrower_history = self.client.get(
            "/applications",
            headers=self._headers(borrower_token),
        )
        self.assertEqual(borrower_history.status_code, 200, borrower_history.text)
        self.assertEqual([row["id"] for row in borrower_history.json()], [application_id])

        other_borrower_token = self._register("other-borrower@example.com", "borrower")
        self.assertEqual(
            self.client.get(
                "/applications",
                headers=self._headers(other_borrower_token),
            ).json(),
            [],
        )
        cross_borrower_detail = self.client.get(
            f"/applications/{application_id}",
            headers=self._headers(other_borrower_token),
        )
        self.assertEqual(cross_borrower_detail.status_code, 403, cross_borrower_detail.text)

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
        self.assertEqual(
            scored_application["score_result"]["model_version"],
            "research-v0.1",
        )
        self.assertEqual(
            scored_application["score_result"]["model_governance"]["feature_schema_version"],
            "behavioral-v1",
        )

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
        self.assertEqual(decision_response.json()["status"], "under_review")
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
        self.assertTrue(all(event["actor_email"] is None for event in timeline))
        self.assertTrue(
            all(set(event["details"]).issubset({"status"}) for event in timeline)
        )
        self.assertEqual(timeline[-1]["title"], "Application moved to manual review")

        review_packet_response = self.client.get(
            f"/mfi/applications/{application_id}/review-packet",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(review_packet_response.status_code, 200, review_packet_response.text)
        review_packet = review_packet_response.json()
        self.assertEqual(review_packet["application_id"], application_id)
        self.assertEqual(review_packet["application"]["borrower_email"], "borrower@example.com")
        self.assertEqual(review_packet["analyst_decision"]["decision"], "review")
        self.assertEqual(review_packet["lifecycle"]["status"], "under_review")
        self.assertEqual(review_packet["lifecycle"]["scoring_action"], "rescore")
        self.assertEqual(review_packet["lifecycle"]["allowed_decisions"], ["approve", "decline"])
        self.assertEqual(len(review_packet["decision_history"]), 1)
        self.assertEqual(review_packet["affordability"]["completeness"], 1.0)
        self.assertAlmostEqual(
            review_packet["affordability"]["debt_to_income_ratio"],
            650_000 / 4_200_000,
        )
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
        self.assertIn(
            "application_id,organization_id,borrower_email,status",
            csv_text,
        )
        self.assertIn(application_id, csv_text)
        self.assertIn("borrower@example.com", csv_text)
        self.assertIn("balanced_review", csv_text)

        admin_token = self._register("admin@example.com", "admin")
        model_status = self.client.get(
            "/mfi/model-status",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(model_status.status_code, 200, model_status.text)
        self.assertTrue(model_status.json()["scoring_allowed"])
        self.assertEqual(
            model_status.json()["active_model"]["version"],
            "research-v0.1",
        )

        registered_model = self.client.post(
            "/admin/model-versions",
            headers=self._headers(admin_token),
            json={
                "version": "research-v0.2",
                "model_name": "Logistic Regression",
                "feature_schema_version": "behavioral-v2",
                "training_data_label": "synthetic-credit-risk-v2",
                "random_state": 77,
                "metrics": {"roc_auc": 0.82, "brier_score": 0.18},
                "limitations": [
                    "Synthetic validation only.",
                    "Requires human decision review.",
                ],
            },
        )
        self.assertEqual(registered_model.status_code, 201, registered_model.text)
        self.assertEqual(registered_model.json()["lifecycle_status"], "candidate")

        activated_model = self.client.post(
            "/admin/model-versions/research-v0.2/activate",
            headers=self._headers(admin_token),
        )
        self.assertEqual(activated_model.status_code, 200, activated_model.text)
        self.assertTrue(activated_model.json()["is_active"])

        model_versions = self.client.get(
            "/admin/model-versions",
            headers=self._headers(admin_token),
        )
        self.assertEqual(model_versions.status_code, 200, model_versions.text)
        self.assertEqual(len(model_versions.json()), 2)
        self.assertEqual(model_versions.json()[0]["version"], "research-v0.2")

        stale_packet_response = self.client.get(
            f"/mfi/applications/{application_id}/review-packet",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(stale_packet_response.status_code, 200, stale_packet_response.text)
        stale_packet = stale_packet_response.json()
        self.assertIn("stale_model_version", stale_packet["governance_flags"])
        self.assertFalse(stale_packet["model_summary"]["is_current_active"])
        self.assertTrue(
            any(item["code"] == "rescore_current_model" for item in stale_packet["checklist"])
        )

        rescored_response = self.client.post(
            f"/mfi/applications/{application_id}/score",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(rescored_response.status_code, 200, rescored_response.text)
        self.assertEqual(rescored_response.json()["status"], "under_review")
        rescored = rescored_response.json()["score_result"]
        self.assertEqual(rescored["model_version"], "research-v0.2")
        self.assertEqual(rescored["model_governance"]["random_state"], 77)

        current_packet = self.client.get(
            f"/mfi/applications/{application_id}/review-packet",
            headers=self._headers(analyst_token),
        ).json()
        self.assertNotIn("stale_model_version", current_packet["governance_flags"])
        self.assertTrue(current_packet["model_summary"]["is_current_active"])

        final_decision = self.client.post(
            f"/mfi/applications/{application_id}/decision",
            headers=self._headers(analyst_token),
            json={
                "decision": "approve",
                "policy_name": "balanced_review",
                "note": "Affordability evidence verified.",
            },
        )
        self.assertEqual(final_decision.status_code, 200, final_decision.text)
        self.assertEqual(final_decision.json()["status"], "approved")
        final_packet = self.client.get(
            f"/mfi/applications/{application_id}/review-packet",
            headers=self._headers(analyst_token),
        ).json()
        self.assertTrue(final_packet["lifecycle"]["terminal"])
        self.assertIsNone(final_packet["lifecycle"]["scoring_action"])
        self.assertEqual(final_packet["lifecycle"]["allowed_decisions"], [])
        self.assertEqual(
            [row["decision"] for row in final_packet["decision_history"]],
            ["review", "approve"],
        )

        terminal_rescore = self.client.post(
            f"/mfi/applications/{application_id}/score",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(terminal_rescore.status_code, 409, terminal_rescore.text)
        terminal_reversal = self.client.post(
            f"/mfi/applications/{application_id}/decision",
            headers=self._headers(analyst_token),
            json={
                "decision": "decline",
                "policy_name": "balanced_review",
                "note": "Attempted reversal.",
            },
        )
        self.assertEqual(terminal_reversal.status_code, 409, terminal_reversal.text)

        final_borrower_history = self.client.get(
            "/applications",
            headers=self._headers(borrower_token),
        ).json()
        self.assertEqual(final_borrower_history[0]["status"], "approved")
        self.assertTrue(final_borrower_history[0]["terminal"])
        final_borrower_timeline = self.client.get(
            f"/applications/{application_id}/timeline",
            headers=self._headers(borrower_token),
        ).json()
        self.assertEqual(final_borrower_timeline[-1]["title"], "Application approved")
        self.assertIn(
            "application_rescored",
            [event["action"] for event in final_borrower_timeline],
        )

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
        self.assertTrue(
            any(event["action"] == "model_version_registered" for event in audit_response.json())
        )
        self.assertTrue(
            any(event["action"] == "model_version_activated" for event in audit_response.json())
        )
        application_created = next(
            event
            for event in audit_response.json()
            if event["action"] == "application_created"
        )
        self.assertTrue(application_created["details"]["consent_confirmed"])
        self.assertEqual(
            application_created["details"]["consent_version"],
            "synthetic-demo-v1",
        )

    def test_openapi_exposes_product_response_schemas(self) -> None:
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200, response.text)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("ApplicationDecisionCreate", schemas)
        self.assertIn("LogoutResponse", schemas)
        self.assertIn("StaffUserCreate", schemas)
        self.assertIn("OrganizationCreate", schemas)
        self.assertIn("OrganizationPublic", schemas)
        self.assertIn("ModelVersionCreate", schemas)
        self.assertIn("ModelVersionPublic", schemas)
        self.assertIn("ModelStatusResponse", schemas)
        self.assertIn("ApplicationDecisionResponse", schemas)
        self.assertIn("ApplicationTimelineEventResponse", schemas)
        self.assertIn("BorrowerApplicationResponse", schemas)
        self.assertIn("ApplicationLifecycleSummary", schemas)
        self.assertIn("AffordabilitySnapshot", schemas)
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
        self.assertIn("PortfolioSimulationRequest", schemas)
        self.assertIn("PortfolioSimulationResponse", schemas)
        self.assertIn("PortfolioSimulationScenario", schemas)
        self.assertIn("SimulationDistribution", schemas)
        self.assertIn("SimulationPolicySummary", schemas)
        self.assertIn("SimulationAssumptions", schemas)
        self.assertIn("SimulationDiagnostics", schemas)
        self.assertIn("PortfolioSimulationScenarioSummary", schemas)
        self.assertIn("PortfolioSimulationSummary", schemas)
        self.assertIn("AuditEventResponse", schemas)
        self.assertIn("ClearApplicationsResponse", schemas)
        self.assertIn("PilotReadinessResponse", schemas)
        self.assertIn("PilotDataClassRow", schemas)

    def test_pilot_readiness_endpoint_defines_minimum_data_contract(self) -> None:
        response = self.client.get("/governance/pilot-readiness")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "planning_only")
        self.assertIn("Pavlodar", payload["region"])
        self.assertIn("minimum-data pilot", payload["privacy_note"])
        self.assertTrue(
            any(row["data_class"] == "Late payment count" for row in payload["data_classes"])
        )
        self.assertTrue(
            any(row["model_use"] == "audit only" for row in payload["data_classes"])
        )
        self.assertTrue(
            any("raw bank statements" in item for item in payload["forbidden_data"])
        )
        self.assertTrue(
            any("late_payment_count" in item for item in payload["validation_questions"])
        )
        self.assertTrue(
            any(
                "segment/fairness reporting" in item
                for item in payload["first_pilot_success_criteria"]
            )
        )

    def test_application_boundary_enforces_consent_and_rejects_sensitive_fields(self) -> None:
        borrower_token = self._register("privacy-borrower@example.com", "borrower")
        headers = self._headers(borrower_token)
        safe_payload = {
            "requested_amount": 245_600,
            "purpose": "equipment repair",
            "district": "Bayanaul",
            "settlement_type": "rural",
            "organization_id": TEST_ORGANIZATION_ID,
            "behavioral_signals": {
                "annual_income": 4_100_000,
                "mobile_banking_logins": 12,
                "late_payment_count": 0,
            },
        }

        missing_consent = self.client.post(
            "/applications",
            headers=headers,
            json=safe_payload,
        )
        self.assertEqual(missing_consent.status_code, 422, missing_consent.text)
        self.assertIn("consent", missing_consent.json()["detail"])

        missing_consent_version = self.client.post(
            "/applications",
            headers=headers,
            json={**safe_payload, "consent_confirmed": True},
        )
        self.assertEqual(
            missing_consent_version.status_code,
            422,
            missing_consent_version.text,
        )
        self.assertIn("consent version", missing_consent_version.json()["detail"])

        sensitive_payload = {
            **safe_payload,
            "consent_confirmed": True,
            "consent_version": "synthetic-demo-v1",
            "behavioral_signals": {
                **safe_payload["behavioral_signals"],
                "identity": {"passport_number": "demo-value"},
            },
        }
        sensitive_response = self.client.post(
            "/applications",
            headers=headers,
            json=sensitive_payload,
        )
        self.assertEqual(sensitive_response.status_code, 422, sensitive_response.text)
        self.assertIn(
            "behavioral_signals.identity.passport_number",
            sensitive_response.json()["detail"]["forbidden_fields"],
        )

        safe_payload["consent_confirmed"] = True
        safe_payload["consent_version"] = "synthetic-demo-v1"
        accepted = self.client.post(
            "/applications",
            headers=headers,
            json=safe_payload,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)

    def test_logout_revokes_backend_session(self) -> None:
        token = self._register("logout@example.com", "borrower")
        headers = self._headers(token)

        self.assertEqual(self.client.get("/me", headers=headers).status_code, 200)
        logout_response = self.client.post("/auth/logout", headers=headers)
        self.assertEqual(logout_response.status_code, 200, logout_response.text)
        self.assertTrue(logout_response.json()["revoked"])
        self.assertEqual(self.client.get("/me", headers=headers).status_code, 401)

        admin_token = self._register("logout-admin@example.com", "admin")
        audit_response = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        )
        self.assertTrue(
            any(event["action"] == "user_logged_out" for event in audit_response.json())
        )

    def test_public_registration_enforces_borrower_role_and_password_policy(self) -> None:
        weak_password = self.client.post(
            "/auth/register",
            json={
                "email": "weak@example.com",
                "password": "password123",
                "role": "borrower",
            },
        )
        self.assertEqual(weak_password.status_code, 422, weak_password.text)
        self.assertIn("registration policy", weak_password.json()["detail"]["message"])

        privileged_role = self.client.post(
            "/auth/register",
            json={
                "email": "self-admin@example.com",
                "password": TEST_PASSWORD,
                "role": "admin",
            },
        )
        self.assertEqual(privileged_role.status_code, 403, privileged_role.text)
        self.assertIn("borrower accounts", privileged_role.json()["detail"])

        borrower = self.client.post(
            "/auth/register",
            json={
                "email": "new-borrower@example.com",
                "password": TEST_PASSWORD,
                "role": "borrower",
            },
        )
        self.assertEqual(borrower.status_code, 200, borrower.text)
        self.assertEqual(borrower.json()["role"], "borrower")

    def test_login_rate_limit_blocks_repeated_failures(self) -> None:
        self.repository.create_user(
            "limited@example.com",
            hash_password(TEST_PASSWORD),
            "borrower",
        )

        for _attempt in range(2):
            response = self.client.post(
                "/auth/login",
                json={"email": "limited@example.com", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 401, response.text)

        blocked = self.client.post(
            "/auth/login",
            json={"email": "limited@example.com", "password": "wrong-password"},
        )
        self.assertEqual(blocked.status_code, 429, blocked.text)
        self.assertEqual(blocked.headers["retry-after"], "120")

        still_blocked = self.client.post(
            "/auth/login",
            json={"email": "limited@example.com", "password": TEST_PASSWORD},
        )
        self.assertEqual(still_blocked.status_code, 429, still_blocked.text)

    def test_admin_can_provision_audited_mfi_analyst(self) -> None:
        borrower_token = self._register("regular@example.com", "borrower")
        forbidden = self.client.post(
            "/admin/users",
            headers=self._headers(borrower_token),
            json={
                "email": "blocked-analyst@example.com",
                "password": TEST_PASSWORD,
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
            },
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        admin_token = self._register("provisioning-admin@example.com", "admin")
        created = self.client.post(
            "/admin/users",
            headers=self._headers(admin_token),
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["role"], "mfi_analyst")
        self.assertEqual(created.json()["organization_id"], TEST_ORGANIZATION_ID)
        self.assertNotIn("password", created.json())

        users = self.client.get(
            "/admin/users",
            headers=self._headers(admin_token),
        )
        self.assertEqual(users.status_code, 200, users.text)
        self.assertTrue(
            any(user["email"] == "new-analyst@example.com" for user in users.json())
        )
        self.assertTrue(all("password_hash" not in user for user in users.json()))

        analyst_login = self.client.post(
            "/auth/login",
            json={"email": "new-analyst@example.com", "password": TEST_PASSWORD},
        )
        self.assertEqual(analyst_login.status_code, 200, analyst_login.text)
        self.assertEqual(analyst_login.json()["role"], "mfi_analyst")

        audit = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        ).json()
        provisioning_event = next(
            event for event in audit if event["action"] == "staff_user_created"
        )
        self.assertEqual(provisioning_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(provisioning_event["entity_id"], "new-analyst@example.com")

    def test_admin_can_create_publicly_listed_organization(self) -> None:
        public_before = self.client.get("/organizations")
        self.assertEqual(public_before.status_code, 200, public_before.text)
        self.assertEqual(len(public_before.json()), 2)

        borrower_token = self._register("org-borrower@example.com", "borrower")
        forbidden = self.client.post(
            "/admin/organizations",
            headers=self._headers(borrower_token),
            json={
                "id": "mfi-c",
                "name": "MFI C",
                "region": "Pavlodar region",
            },
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        admin_token = self._register("org-admin@example.com", "admin")
        created = self.client.post(
            "/admin/organizations",
            headers=self._headers(admin_token),
            json={
                "id": "MFI-C",
                "name": "MFI C",
                "region": "Pavlodar region",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["id"], "mfi-c")

        public_after = self.client.get("/organizations").json()
        self.assertTrue(any(item["id"] == "mfi-c" for item in public_after))

    def test_mfi_analysts_are_isolated_by_organization(self) -> None:
        borrower_token = self._register("tenant-borrower@example.com", "borrower")
        borrower_headers = self._headers(borrower_token)

        application_ids: dict[str, str] = {}
        for organization_id in (TEST_ORGANIZATION_ID, SECOND_ORGANIZATION_ID):
            response = self.client.post(
                "/applications",
                headers=borrower_headers,
                json={
                    "requested_amount": 250_000,
                    "purpose": "inventory",
                    "district": "Pavlodar city",
                    "settlement_type": "urban",
                    "organization_id": organization_id,
                    "consent_confirmed": True,
                    "consent_version": "synthetic-demo-v1",
                    "behavioral_signals": {
                        "annual_income": 4_000_000,
                        "late_payment_count": 0,
                    },
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            application_ids[organization_id] = response.json()["id"]

        analyst_a_token = self._register("analyst-a@example.com", "mfi_analyst")
        self.repository.create_user(
            "analyst-b@example.com",
            hash_password(TEST_PASSWORD),
            "mfi_analyst",
            SECOND_ORGANIZATION_ID,
        )
        analyst_b_login = self.client.post(
            "/auth/login",
            json={"email": "analyst-b@example.com", "password": TEST_PASSWORD},
        )
        analyst_b_token = analyst_b_login.json()["access_token"]

        queue_a = self.client.get(
            "/mfi/applications",
            headers=self._headers(analyst_a_token),
        ).json()
        queue_b = self.client.get(
            "/mfi/applications",
            headers=self._headers(analyst_b_token),
        ).json()
        self.assertEqual(
            {item["organization_id"] for item in queue_a},
            {TEST_ORGANIZATION_ID},
        )
        self.assertEqual(
            {item["organization_id"] for item in queue_b},
            {SECOND_ORGANIZATION_ID},
        )

        cross_tenant_score = self.client.post(
            f"/mfi/applications/{application_ids[SECOND_ORGANIZATION_ID]}/score",
            headers=self._headers(analyst_a_token),
        )
        self.assertEqual(cross_tenant_score.status_code, 403, cross_tenant_score.text)

        admin_token = self._register("tenant-admin@example.com", "admin")
        admin_queue = self.client.get(
            "/mfi/applications",
            headers=self._headers(admin_token),
        ).json()
        self.assertEqual(len(admin_queue), 2)

    def test_monte_carlo_simulation_is_reproducible_scoped_and_audited(self) -> None:
        self.repository.create_user(
            "simulation-borrower@example.com",
            hash_password(TEST_PASSWORD),
            "borrower",
        )
        analyst_token = self._register("simulation-analyst@example.com", "mfi_analyst")

        scored_counts = {TEST_ORGANIZATION_ID: 3, SECOND_ORGANIZATION_ID: 2}
        for organization_id, count in scored_counts.items():
            for index in range(count):
                application_id = f"sim-{organization_id}-{index}"
                self.repository.create_application(
                    application_id=application_id,
                    borrower_email="simulation-borrower@example.com",
                    requested_amount=200_000 + index * 50_000,
                    purpose="simulation fixture",
                    district="Pavlodar city",
                    settlement_type="urban",
                    behavioral_signals={"late_payment_count": index},
                    organization_id=organization_id,
                )
                self.repository.update_application_score(
                    application_id=application_id,
                    actor_email="simulation-analyst@example.com",
                    score_result={
                        "model_name": "Logistic Regression",
                        "model_version": "research-v0.1",
                        "model_governance": {},
                        "high_risk_probability": 0.15 + index * 0.2,
                        "risk_band": "medium",
                        "warnings": [],
                    },
                )

        self.repository.create_application(
            application_id="sim-unscored",
            borrower_email="simulation-borrower@example.com",
            requested_amount=175_000,
            purpose="unscored fixture",
            district="Bayanaul",
            settlement_type="rural",
            behavioral_signals={},
            organization_id=TEST_ORGANIZATION_ID,
        )

        request_payload = {
            "iterations": 500,
            "seed": 991,
            "policy": "balanced_review",
            "scenarios": ["baseline", "adverse", "severe"],
            "review_approval_rate": 0.6,
            "interest_margin_rate": 0.22,
            "loss_given_default": 0.65,
            "operating_cost_per_approved": 5_000,
            "macro_volatility": 0.25,
            "calibration_volatility": 0.15,
        }
        first = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(analyst_token),
            json=request_payload,
        )
        second = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(analyst_token),
            json=request_payload,
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        first_payload = first.json()
        second_payload = second.json()
        self.assertEqual(first_payload["organization_id"], TEST_ORGANIZATION_ID)
        self.assertEqual(first_payload["application_count"], 4)
        self.assertEqual(first_payload["scored_application_count"], 3)
        self.assertEqual(first_payload["unscored_application_count"], 1)
        self.assertTrue(any("excluded" in warning for warning in first_payload["warnings"]))
        self.assertEqual(first_payload["scenarios"], second_payload["scenarios"])
        self.assertEqual(first_payload["policy"], second_payload["policy"])
        self.assertEqual(
            first_payload["portfolio_fingerprint"],
            second_payload["portfolio_fingerprint"],
        )
        self.assertEqual(len(first_payload["portfolio_fingerprint"]), 64)
        self.assertEqual(len(first_payload["scenarios"]), 3)
        self.assertIn("scenario-planning", first_payload["note"].lower())
        self.assertIn("diagnostics", first_payload["scenarios"][0])

        history = self.client.get(
            "/mfi/simulations",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()), 2)
        self.assertEqual(
            history.json()[0]["portfolio_fingerprint"],
            first_payload["portfolio_fingerprint"],
        )
        stored_detail = self.client.get(
            f"/mfi/simulations/{first_payload['simulation_id']}",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(stored_detail.status_code, 200, stored_detail.text)
        self.assertEqual(stored_detail.json()["scenarios"], first_payload["scenarios"])

        self.repository.create_user(
            "simulation-other-analyst@example.com",
            hash_password(TEST_PASSWORD),
            "mfi_analyst",
            SECOND_ORGANIZATION_ID,
        )
        other_login = self.client.post(
            "/auth/login",
            json={
                "email": "simulation-other-analyst@example.com",
                "password": TEST_PASSWORD,
            },
        )
        cross_tenant_history = self.client.get(
            f"/mfi/simulations/{first_payload['simulation_id']}",
            headers=self._headers(other_login.json()["access_token"]),
        )
        self.assertEqual(cross_tenant_history.status_code, 403, cross_tenant_history.text)

        borrower_login = self.client.post(
            "/auth/login",
            json={"email": "simulation-borrower@example.com", "password": TEST_PASSWORD},
        )
        self.assertEqual(borrower_login.status_code, 200, borrower_login.text)
        forbidden = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(borrower_login.json()["access_token"]),
            json=request_payload,
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        invalid = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(analyst_token),
            json={**request_payload, "iterations": 99},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)

        self.repository.create_model_version(
            version="simulation-v0.2",
            model_name="Logistic Regression",
            feature_schema_version="behavioral-v2",
            training_data_label="simulation-fixture-v2",
            random_state=77,
            metrics={"roc_auc": 0.81},
            limitations=["Synthetic test fixture."],
            created_by="simulation-admin@example.com",
        )
        self.repository.activate_model_version("simulation-v0.2")
        stale_score_run = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(analyst_token),
            json={**request_payload, "scenarios": ["baseline"]},
        )
        self.assertEqual(stale_score_run.status_code, 200, stale_score_run.text)
        self.assertTrue(
            any("active model version simulation-v0.2" in warning for warning in stale_score_run.json()["warnings"])
        )

        admin_token = self._register("simulation-admin@example.com", "admin")
        admin_result = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(admin_token),
            json={**request_payload, "scenarios": ["baseline"]},
        )
        self.assertEqual(admin_result.status_code, 200, admin_result.text)
        self.assertIsNone(admin_result.json()["organization_id"])
        self.assertEqual(admin_result.json()["scored_application_count"], 5)
        admin_history = self.client.get(
            "/mfi/simulations",
            headers=self._headers(admin_token),
        )
        self.assertEqual(admin_history.status_code, 200, admin_history.text)
        self.assertEqual(len(admin_history.json()), 4)

        audit = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        ).json()
        simulation_events = [
            event for event in audit if event["action"] == "portfolio_simulation_run"
        ]
        self.assertEqual(len(simulation_events), 4)
        self.assertEqual(simulation_events[-1]["details"]["seed"], 991)
        self.assertTrue(simulation_events[-1]["details"]["scenario_summary"])

    def test_monte_carlo_requires_a_scored_portfolio(self) -> None:
        analyst_token = self._register("empty-simulation@example.com", "mfi_analyst")
        response = self.client.post(
            "/mfi/simulations/portfolio",
            headers=self._headers(analyst_token),
            json={"iterations": 100, "seed": 1},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("scored application", response.json()["detail"])

    def test_cors_headers_allow_only_trusted_frontends(self) -> None:
        local_response = self.client.get(
            "/health",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

        untrusted_response = self.client.get(
            "/health",
            headers={"Origin": "https://untrusted.example"},
        )

        self.assertEqual(local_response.status_code, 200, local_response.text)
        self.assertEqual(
            local_response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )
        self.assertEqual(untrusted_response.status_code, 200, untrusted_response.text)
        self.assertNotIn("access-control-allow-origin", untrusted_response.headers)

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
                "organization_id": TEST_ORGANIZATION_ID,
                "consent_confirmed": True,
                "consent_version": "synthetic-demo-v1",
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
