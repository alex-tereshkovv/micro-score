from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

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
TEST_MFA_CODE = "246810"
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
            self.repository.attest_user_mfa(
                email,
                email,
                "prototype_mfa_code",
            )
            response = self.client.post(
                "/auth/login",
                json={"email": email, "password": TEST_PASSWORD, "mfa_code": TEST_MFA_CODE},
            )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _webhook_headers(body: bytes, secret: str = "webhook-secret") -> dict[str, str]:
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return {
            "content-type": "application/json",
            "x-microscore-delivery-timestamp": timestamp,
            "x-microscore-delivery-signature": f"sha256={signature}",
        }

    def test_full_borrower_mfi_admin_flow(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertIn("api-test.sqlite3", health.json()["database"])
        storage = health.json()["storage"]
        self.assertEqual(storage["backend"], "sqlite")
        self.assertEqual(storage["status"], "ready")
        self.assertFalse(storage["production_ready"])
        self.assertIn("loan_applications", storage["required_tables"])
        self.assertIn("audit_events.details_json", storage["json_columns"])
        self.assertIn(
            "loan_applications.organization_id",
            storage["tenant_scoped_tables"],
        )
        self.assertEqual(storage["postgresql_migration_status"], "planned")

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

        pre_decision_packet_response = self.client.get(
            f"/mfi/applications/{application_id}/review-packet",
            headers=self._headers(analyst_token),
        )
        self.assertEqual(
            pre_decision_packet_response.status_code,
            200,
            pre_decision_packet_response.text,
        )
        pre_decision_packet = pre_decision_packet_response.json()
        self.assertEqual(pre_decision_packet["lifecycle"]["status"], "scored")
        self.assertEqual(pre_decision_packet["lifecycle"]["scoring_action"], "rescore")
        self.assertEqual(
            pre_decision_packet["lifecycle"]["allowed_decisions"],
            ["review", "approve", "decline"],
        )
        required_check_codes = {
            row["code"]
            for row in pre_decision_packet["checklist"]
            if row["status"] == "required"
        }
        self.assertIn("verify_affordability", required_check_codes)
        self.assertIn("record_human_decision", required_check_codes)

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
        self.assertIn("AuthResponse", schemas)
        self.assertIn("MeResponse", schemas)
        self.assertIn("LogoutResponse", schemas)
        self.assertIn("StorageReadinessResponse", schemas)
        self.assertIn("StorageCapabilityResponse", schemas)
        self.assertIn("IdentityReadinessComponent", schemas)
        self.assertIn("IdentityReadinessControl", schemas)
        self.assertIn("IdentityReadinessResponse", schemas)
        self.assertIn("MfaAttestationCreate", schemas)
        self.assertIn("MfaAttestationResponse", schemas)
        self.assertIn("MfaReadinessAccount", schemas)
        self.assertIn("MfaReadinessResponse", schemas)
        self.assertIn("SecurityReadinessCheck", schemas)
        self.assertIn("SecurityReadinessResponse", schemas)
        self.assertIn("StaffUserCreate", schemas)
        self.assertIn("StaffUserDisableResponse", schemas)
        self.assertIn("StaffUserReactivateResponse", schemas)
        self.assertIn("StaffInviteCreate", schemas)
        self.assertIn("StaffInviteAccept", schemas)
        self.assertIn("StaffInviteResponse", schemas)
        self.assertIn("StaffInviteCreatedResponse", schemas)
        self.assertIn("StaffInviteDeliveryCreate", schemas)
        self.assertIn("StaffInviteDeliveryAttemptResponse", schemas)
        self.assertIn("StaffInviteDeliveryWebhookCreate", schemas)
        self.assertIn("StaffInviteDeliveryWebhookEventResponse", schemas)
        self.assertIn("StaffInviteDeliveryAdapterReadinessResponse", schemas)
        self.assertIn("StaffInviteDeliveryOutboxResponse", schemas)
        self.assertIn("StaffInviteDeliveryOutboxRunCreate", schemas)
        self.assertIn("StaffInviteDeliveryOutboxRunResponse", schemas)
        self.assertIn("StaffInviteDeliveryResponse", schemas)
        self.assertIn("StaffInviteRotateCreate", schemas)
        self.assertIn("StaffInviteHealthResponse", schemas)
        self.assertIn("OrganizationCreate", schemas)
        self.assertIn("OrganizationPublic", schemas)
        self.assertIn("ModelVersionCreate", schemas)
        self.assertIn("ModelVersionPublic", schemas)
        self.assertIn("ModelStatusResponse", schemas)
        self.assertIn("ApplicationCreate", schemas)
        self.assertIn("BehavioralSignalsCreate", schemas)
        self.assertFalse(schemas["ApplicationCreate"]["additionalProperties"])
        self.assertFalse(schemas["BehavioralSignalsCreate"]["additionalProperties"])
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
        self.assertIn("session_expires_at", schemas["AuthResponse"]["properties"])
        self.assertIn("session_ttl_seconds", schemas["AuthResponse"]["properties"])
        self.assertIn("storage", schemas["HealthResponse"]["properties"])
        storage_properties = schemas["StorageReadinessResponse"]["properties"]
        self.assertIn("postgresql_migration_checklist", storage_properties)
        self.assertIn("tenant_scoped_tables", storage_properties)
        identity_properties = schemas["IdentityReadinessResponse"]["properties"]
        self.assertIn("auth_provider_mode", identity_properties)
        self.assertIn("production_blockers", identity_properties)
        self.assertIn("next_required_controls", identity_properties)
        delivery_readiness_properties = schemas["StaffInviteDeliveryReadinessResponse"][
            "properties"
        ]
        self.assertIn("configured_provider", delivery_readiness_properties)
        self.assertIn("invite_url_https", delivery_readiness_properties)
        self.assertIn("production_blockers", delivery_readiness_properties)
        self.assertIn("providers", delivery_readiness_properties)
        self.assertIn("StaffInviteDeliveryProviderProfile", schemas)
        provider_profile_properties = schemas["StaffInviteDeliveryProviderProfile"][
            "properties"
        ]
        self.assertIn("configuration_status", provider_profile_properties)
        self.assertIn("configuration_ready", provider_profile_properties)
        self.assertIn("required_environment", provider_profile_properties)
        self.assertIn("configured_environment", provider_profile_properties)
        self.assertIn("missing_environment", provider_profile_properties)
        self.assertIn("configuration_warnings", provider_profile_properties)
        self.assertIn("mfa_code", schemas["LoginRequest"]["properties"])
        self.assertIn("mfa_code", schemas["StaffInviteAccept"]["properties"])
        self.assertIn("session_expires_at", schemas["MeResponse"]["properties"])
        self.assertIn("session_ttl_seconds", schemas["MeResponse"]["properties"])
        self.assertIn("disabled_at", schemas["UserPublic"]["properties"])
        self.assertIn("disabled_by", schemas["UserPublic"]["properties"])
        self.assertIn("mfa_attested_at", schemas["UserPublic"]["properties"])
        self.assertIn("mfa_attested_by", schemas["UserPublic"]["properties"])
        self.assertIn("mfa_method", schemas["UserPublic"]["properties"])
        self.assertIn("missing_mfa_count", schemas["MfaReadinessResponse"]["properties"])
        self.assertIn("limitation", schemas["MfaReadinessResponse"]["properties"])
        self.assertIn("blockers_count", schemas["SecurityReadinessResponse"]["properties"])
        self.assertIn("recommended_actions", schemas["SecurityReadinessResponse"]["properties"])
        self.assertIn("checks", schemas["SecurityReadinessResponse"]["properties"])
        self.assertIn("revoked_session_count", schemas["StaffUserDisableResponse"]["properties"])
        self.assertIn("was_already_active", schemas["StaffUserReactivateResponse"]["properties"])
        self.assertIn("session_id", schemas["StaffSessionResponse"]["properties"])
        self.assertIn("session_preview", schemas["StaffSessionResponse"]["properties"])
        self.assertIn("is_current_session", schemas["StaffSessionResponse"]["properties"])
        self.assertNotIn("token", schemas["StaffSessionResponse"]["properties"])
        self.assertIn("revoked", schemas["StaffSessionRevokeResponse"]["properties"])
        self.assertIn("token_id", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("token_preview", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("delivered_at", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("delivery_channel", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("delivery_url_base", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("delivery_attempt_count", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("last_delivery_status", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("delivery_event_count", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("last_delivery_event_type", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("queue_delivery", schemas["StaffInviteCreate"]["properties"])
        self.assertIn("delivery_provider", schemas["StaffInviteCreate"]["properties"])
        self.assertIn("provider", schemas["StaffInviteDeliveryRetryCreate"]["properties"])
        self.assertIn("delivery_attempt", schemas["StaffInviteCreatedResponse"]["properties"])
        self.assertIn("delivery_attempt", schemas["StaffInviteDeliveryResponse"]["properties"])
        self.assertIn("provider", schemas["StaffInviteDeliveryAttemptResponse"]["properties"])
        self.assertIn("invite_token_id", schemas["StaffInviteDeliveryAttemptResponse"]["properties"])
        attempt_properties = schemas["StaffInviteDeliveryAttemptResponse"]["properties"]
        self.assertIn("worker_status", attempt_properties)
        self.assertIn("worker_attempt_count", attempt_properties)
        self.assertIn("next_worker_run_at", attempt_properties)
        self.assertIn("dead_letter_at", attempt_properties)
        self.assertIn("last_worker_error", attempt_properties)
        outbox_properties = schemas["StaffInviteDeliveryOutboxResponse"]["properties"]
        self.assertIn("due_count", outbox_properties)
        self.assertIn("dead_letter_count", outbox_properties)
        self.assertIn("items", outbox_properties)
        self.assertIn("limitation", outbox_properties)
        adapter_properties = schemas["StaffInviteDeliveryAdapterReadinessResponse"][
            "properties"
        ]
        self.assertIn("external_send_enabled", adapter_properties)
        self.assertIn("idempotency_key_strategy", adapter_properties)
        self.assertIn("safe_payload_fields", adapter_properties)
        self.assertIn("forbidden_payload_fields", adapter_properties)
        self.assertIn("secret_rotation_ready", adapter_properties)
        outbox_run_properties = schemas["StaffInviteDeliveryOutboxRunResponse"]["properties"]
        self.assertIn("processed_count", outbox_run_properties)
        self.assertIn("dead_lettered_count", outbox_run_properties)
        self.assertIn("results", outbox_run_properties)
        webhook_properties = schemas["StaffInviteDeliveryWebhookEventResponse"][
            "properties"
        ]
        self.assertIn("provider_event_id", webhook_properties)
        self.assertIn("mapped_attempt_status", webhook_properties)
        self.assertIn("delivery_recorded", webhook_properties)
        self.assertIn("metadata", schemas["StaffInviteDeliveryWebhookCreate"]["properties"])
        self.assertNotIn("token", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("token", schemas["StaffInviteCreatedResponse"]["properties"])
        self.assertIn("invite_url", schemas["StaffInviteCreatedResponse"]["properties"])
        self.assertIn(
            "was_already_delivered",
            schemas["StaffInviteDeliveryResponse"]["properties"],
        )
        self.assertIn("revoked_at", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("revoked_by", schemas["StaffInviteResponse"]["properties"])
        self.assertIn("status", schemas["StaffInviteHealthResponse"]["properties"])
        self.assertIn("expiring_soon_count", schemas["StaffInviteHealthResponse"]["properties"])
        self.assertIn("action_required_count", schemas["StaffInviteHealthResponse"]["properties"])
        self.assertIn("recommended_action", schemas["StaffInviteHealthResponse"]["properties"])
        paths = response.json()["paths"]
        self.assertIn("/admin/security/readiness", paths)
        self.assertIn("/admin/security/identity-readiness", paths)
        self.assertIn("/admin/security/mfa-readiness", paths)
        self.assertIn("/admin/users/{email}/mfa/attest", paths)
        self.assertIn("/admin/staff-sessions", paths)
        self.assertIn("/admin/staff-sessions/{session_id}", paths)
        self.assertIn("/admin/staff-invites", paths)
        self.assertIn("/admin/staff-invites/health", paths)
        self.assertIn("/admin/staff-invites/delivery-readiness", paths)
        self.assertIn("/admin/staff-invites/delivery-adapter-readiness", paths)
        self.assertIn("/admin/staff-invites/delivery-outbox", paths)
        self.assertIn("/admin/staff-invites/delivery-outbox/run", paths)
        self.assertIn("/admin/staff-invites/{token_id}/delivery", paths)
        self.assertIn("/admin/staff-invites/{token_id}/delivery-attempts", paths)
        self.assertIn("/admin/staff-invites/{token_id}/delivery-events", paths)
        self.assertIn("/admin/staff-invites/{token_id}/delivery-attempts/retry", paths)
        self.assertIn("/admin/staff-invites/{token_id}/rotate", paths)
        self.assertIn("/admin/staff-invites/{token_id}", paths)
        self.assertIn("/webhooks/staff-invite-delivery", paths)
        self.assertIn("/auth/accept-staff-invite", paths)
        self.assertIn("/admin/users/{email}/disable", paths)
        self.assertIn("/admin/users/{email}/reactivate", paths)

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
        self.assertIn("behavioral_signals.identity.passport_number", sensitive_response.text)

        safe_payload["consent_confirmed"] = True
        safe_payload["consent_version"] = "synthetic-demo-v1"
        invalid_cases = [
            ({**safe_payload, "requested_amount": 999}, "requested_amount"),
            (
                {**safe_payload, "district": "Aksu", "settlement_type": "urban"},
                "Settlement type for Aksu must be industrial_city",
            ),
            (
                {
                    **safe_payload,
                    "behavioral_signals": {
                        **safe_payload["behavioral_signals"],
                        "num_open_loans": 1.5,
                    },
                },
                "num_open_loans",
            ),
            (
                {
                    **safe_payload,
                    "behavioral_signals": {
                        **safe_payload["behavioral_signals"],
                        "unreviewed_proxy": 1,
                    },
                },
                "unreviewed_proxy",
            ),
            ({**safe_payload, "purpose": "x" * 201}, "purpose"),
        ]
        for invalid_payload, expected_error in invalid_cases:
            with self.subTest(expected_error=expected_error):
                rejected = self.client.post(
                    "/applications",
                    headers=headers,
                    json=invalid_payload,
                )
                self.assertEqual(rejected.status_code, 422, rejected.text)
                self.assertIn(expected_error, rejected.text)

        accepted = self.client.post(
            "/applications",
            headers=headers,
            json=safe_payload,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)

    def test_logout_revokes_backend_session(self) -> None:
        token = self._register("logout@example.com", "borrower")
        headers = self._headers(token)

        me_response = self.client.get("/me", headers=headers)
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertIn("session_expires_at", me_response.json())
        self.assertEqual(me_response.json()["session_ttl_seconds"], 8 * 60 * 60)
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
        self.assertIn("session_expires_at", borrower.json())
        self.assertEqual(borrower.json()["session_ttl_seconds"], 8 * 60 * 60)

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

    def test_identity_readiness_summarizes_production_identity_gaps(self) -> None:
        borrower_token = self._register("identity-borrower@example.com", "borrower")
        forbidden = self.client.get(
            "/admin/security/identity-readiness",
            headers=self._headers(borrower_token),
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        admin_token = self._register("identity-admin@example.com", "admin")
        self.repository.create_user(
            "identity-analyst@example.com",
            hash_password(TEST_PASSWORD),
            "mfi_analyst",
            TEST_ORGANIZATION_ID,
        )

        response = self.client.get(
            "/admin/security/identity-readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["auth_provider_mode"], "local_password_prototype")
        self.assertEqual(payload["invite_delivery_mode"], "local_outbox")
        self.assertEqual(
            payload["mfa_mode"],
            "prototype_shared_code_with_admin_attestation",
        )
        self.assertEqual(
            payload["session_control_mode"],
            "local_bearer_sessions_with_admin_revoke",
        )
        self.assertEqual(payload["rate_limit_mode"], "in_memory_single_process")
        self.assertEqual(payload["storage_backend"], "sqlite")
        self.assertEqual(
            payload["tenant_isolation_mode"],
            "organization_id_scoped_mfi_access",
        )
        self.assertEqual(payload["active_staff_count"], 2)
        self.assertEqual(payload["active_staff_session_count"], 1)
        self.assertEqual(payload["active_pending_invite_count"], 0)

        components = {row["key"]: row for row in payload["components"]}
        self.assertEqual(
            set(components),
            {
                "auth_provider",
                "mfa_posture",
                "invite_delivery",
                "session_control",
                "rate_limit",
                "storage_backend",
                "tenant_isolation",
            },
        )
        self.assertEqual(components["auth_provider"]["status"], "blocker")
        self.assertEqual(components["mfa_posture"]["status"], "blocker")
        self.assertEqual(components["invite_delivery"]["status"], "blocker")
        self.assertEqual(components["session_control"]["status"], "pass")
        self.assertEqual(components["tenant_isolation"]["status"], "pass")

        blocker_keys = {row["key"] for row in payload["production_blockers"]}
        self.assertIn("auth_provider", blocker_keys)
        self.assertIn("mfa_posture", blocker_keys)
        self.assertIn("invite_delivery", blocker_keys)
        self.assertIn("rate_limit", blocker_keys)
        self.assertIn("storage_backend", blocker_keys)
        self.assertTrue(
            all(row["severity"] == "blocker" for row in payload["production_blockers"])
        )
        next_control_keys = {row["key"] for row in payload["next_required_controls"]}
        self.assertIn("invite_delivery", next_control_keys)
        self.assertIn("external IdP", payload["limitation"])

        serialized = json.dumps(payload)
        self.assertNotIn("session_id", serialized)
        self.assertNotIn("session_preview", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn(TEST_MFA_CODE, serialized)

    def test_staff_invite_delivery_readiness_tracks_provider_contract(self) -> None:
        borrower_token = self._register("delivery-readiness-borrower@example.com", "borrower")
        forbidden = self.client.get(
            "/admin/staff-invites/delivery-readiness",
            headers=self._headers(borrower_token),
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        admin_token = self._register("delivery-readiness-admin@example.com", "admin")
        response = self.client.get(
            "/admin/staff-invites/delivery-readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["configured_provider"], "local_outbox")
        self.assertEqual(payload["default_provider"], "local_outbox")
        self.assertEqual(payload["invite_url_base"], "http://127.0.0.1:5173")
        self.assertFalse(payload["invite_url_https"])
        self.assertTrue(payload["invite_url_local"])
        self.assertEqual(payload["active_pending_invite_count"], 0)
        self.assertEqual(payload["undelivered_active_invite_count"], 0)
        self.assertEqual(payload["failed_latest_attempt_count"], 0)

        providers = {row["provider"]: row for row in payload["providers"]}
        self.assertIn("local_outbox", providers)
        self.assertIn("transactional_email", providers)
        self.assertTrue(providers["local_outbox"]["configured"])
        self.assertFalse(providers["local_outbox"]["production_ready"])
        self.assertFalse(providers["local_outbox"]["sends_message"])
        self.assertEqual(providers["local_outbox"]["attempt_status"], "sent")
        self.assertEqual(providers["local_outbox"]["configuration_status"], "not_required")
        self.assertTrue(providers["local_outbox"]["configuration_ready"])
        self.assertEqual(
            providers["transactional_email"]["mode"],
            "transactional_email_contract",
        )
        self.assertTrue(providers["transactional_email"]["requires_external_secret"])
        self.assertEqual(providers["transactional_email"]["configuration_status"], "missing")
        self.assertFalse(providers["transactional_email"]["configuration_ready"])
        self.assertIn(
            "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY",
            providers["transactional_email"]["missing_environment"],
        )
        self.assertIn(
            "MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET",
            providers["transactional_email"]["required_environment"],
        )

        blocker_keys = {row["key"] for row in payload["production_blockers"]}
        self.assertIn("delivery_provider_not_production_ready", blocker_keys)
        self.assertIn("invite_url_not_https", blocker_keys)
        self.assertIn("invite_url_local_origin", blocker_keys)
        self.assertEqual(
            {row["key"] for row in payload["next_required_controls"]},
            blocker_keys,
        )
        self.assertIn("does not expose secret values", payload["limitation"])

        invite = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "delivery-readiness-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
            },
        )
        self.assertEqual(invite.status_code, 201, invite.text)

        with_invite = self.client.get(
            "/admin/staff-invites/delivery-readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(with_invite.status_code, 200, with_invite.text)
        with_invite_payload = with_invite.json()
        self.assertEqual(with_invite_payload["active_pending_invite_count"], 1)
        self.assertEqual(with_invite_payload["undelivered_active_invite_count"], 1)
        self.assertIn(
            "undelivered_active_invites",
            {row["key"] for row in with_invite_payload["production_blockers"]},
        )

    def test_transactional_email_readiness_validates_secret_contract(self) -> None:
        admin_token = self._register("delivery-config-admin@example.com", "admin")

        with patch.dict(
            os.environ,
            {
                "MICROSCORE_INVITE_DELIVERY_PROVIDER": "transactional_email",
                "MICROSCORE_INVITE_WEB_BASE_URL": "https://onboarding.example.com/micro-score",
            },
            clear=False,
        ):
            response = self.client.get(
                "/admin/staff-invites/delivery-readiness",
                headers=self._headers(admin_token),
            )
        self.assertEqual(response.status_code, 200, response.text)
        missing_payload = response.json()
        missing_profile = next(
            row
            for row in missing_payload["providers"]
            if row["provider"] == "transactional_email"
        )
        self.assertTrue(missing_profile["configured"])
        self.assertEqual(missing_profile["configuration_status"], "missing")
        self.assertFalse(missing_profile["configuration_ready"])
        self.assertEqual(missing_payload["configured_provider"], "transactional_email")
        self.assertTrue(missing_payload["invite_url_https"])
        self.assertFalse(missing_payload["invite_url_local"])
        missing_blocker_keys = {
            row["key"] for row in missing_payload["production_blockers"]
        }
        self.assertIn(
            "delivery_provider_configuration_missing",
            missing_blocker_keys,
        )
        self.assertIn(
            "delivery_provider_not_production_ready",
            missing_blocker_keys,
        )

        secret_value = "test-secret-value-should-not-leak"
        with patch.dict(
            os.environ,
            {
                "MICROSCORE_INVITE_DELIVERY_PROVIDER": "transactional_email",
                "MICROSCORE_INVITE_WEB_BASE_URL": "https://onboarding.example.com/micro-score",
                "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY": secret_value,
                "MICROSCORE_TRANSACTIONAL_EMAIL_FROM": "security@example.com",
                "MICROSCORE_TRANSACTIONAL_EMAIL_TEMPLATE_ID": "staff-invite-v1",
                "MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET": "webhook-secret",
                "MICROSCORE_TRANSACTIONAL_EMAIL_API_BASE_URL": "https://email.example.com/api",
            },
            clear=False,
        ):
            configured_response = self.client.get(
                "/admin/staff-invites/delivery-readiness",
                headers=self._headers(admin_token),
            )
        self.assertEqual(configured_response.status_code, 200, configured_response.text)
        configured_payload = configured_response.json()
        configured_profile = next(
            row
            for row in configured_payload["providers"]
            if row["provider"] == "transactional_email"
        )
        self.assertEqual(configured_profile["configuration_status"], "ready")
        self.assertTrue(configured_profile["configuration_ready"])
        self.assertEqual(configured_profile["missing_environment"], [])
        self.assertIn(
            "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY",
            configured_profile["configured_environment"],
        )
        self.assertNotIn(secret_value, json.dumps(configured_payload))
        configured_blocker_keys = {
            row["key"] for row in configured_payload["production_blockers"]
        }
        self.assertNotIn(
            "delivery_provider_configuration_missing",
            configured_blocker_keys,
        )
        self.assertIn(
            "delivery_provider_not_production_ready",
            configured_blocker_keys,
        )

    def test_delivery_adapter_readiness_blocks_external_send_boundary(self) -> None:
        borrower_token = self._register("adapter-readiness-borrower@example.com", "borrower")
        forbidden = self.client.get(
            "/admin/staff-invites/delivery-adapter-readiness",
            headers=self._headers(borrower_token),
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        admin_token = self._register("adapter-readiness-admin@example.com", "admin")
        response = self.client.get(
            "/admin/staff-invites/delivery-adapter-readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["provider"], "transactional_email")
        self.assertFalse(payload["send_adapter_ready"])
        self.assertFalse(payload["external_send_enabled"])
        self.assertFalse(payload["secret_rotation_ready"])
        self.assertEqual(
            payload["idempotency_key_strategy"],
            "sha256(provider:attempt_id:invite_token_id)",
        )
        self.assertIn("adapter_idempotency_key", payload["safe_payload_fields"])
        self.assertIn("raw_invite_token", payload["forbidden_payload_fields"])
        self.assertIn("full_invite_url", payload["forbidden_payload_fields"])
        self.assertIn("attempt_id", payload["webhook_correlation_fields"])
        blocker_keys = {row["key"] for row in payload["blockers"]}
        self.assertIn("external_send_adapter_disabled", blocker_keys)
        self.assertIn("invite_secret_material_not_available", blocker_keys)
        self.assertIn("transactional_email_configuration_missing", blocker_keys)
        self.assertIn("secret_rotation_version_missing", blocker_keys)

        secret_value = "adapter-secret-should-not-leak"
        with patch.dict(
            os.environ,
            {
                "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY": secret_value,
                "MICROSCORE_TRANSACTIONAL_EMAIL_FROM": "security@example.com",
                "MICROSCORE_TRANSACTIONAL_EMAIL_TEMPLATE_ID": "staff-invite-v1",
                "MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET": "webhook-secret",
                "MICROSCORE_TRANSACTIONAL_EMAIL_API_BASE_URL": "https://email.example.com/api",
                "MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION": "2026-07-rotation-a",
                "MICROSCORE_TRANSACTIONAL_EMAIL_SEND_ENABLED": "true",
            },
            clear=False,
        ):
            configured = self.client.get(
                "/admin/staff-invites/delivery-adapter-readiness",
                headers=self._headers(admin_token),
            )
        self.assertEqual(configured.status_code, 200, configured.text)
        configured_payload = configured.json()
        self.assertEqual(configured_payload["status"], "blocked")
        self.assertEqual(configured_payload["configuration_status"], "ready")
        self.assertTrue(configured_payload["configuration_ready"])
        self.assertTrue(configured_payload["secret_rotation_ready"])
        self.assertTrue(configured_payload["external_send_enabled"])
        self.assertFalse(configured_payload["send_adapter_ready"])
        self.assertEqual(configured_payload["missing_environment"], [])
        self.assertIn(
            "MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION",
            configured_payload["configured_environment"],
        )
        configured_blockers = {row["key"] for row in configured_payload["blockers"]}
        configured_warnings = {row["key"] for row in configured_payload["warnings"]}
        self.assertIn("external_send_adapter_disabled", configured_blockers)
        self.assertIn("invite_secret_material_not_available", configured_blockers)
        self.assertNotIn("transactional_email_configuration_missing", configured_blockers)
        self.assertNotIn("secret_rotation_version_missing", configured_blockers)
        self.assertIn("external_send_flag_ignored", configured_warnings)
        self.assertNotIn(secret_value, json.dumps(configured_payload))

    def test_signed_delivery_webhook_records_provider_events(self) -> None:
        admin_token = self._register("delivery-webhook-admin@example.com", "admin")
        invite = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "delivery-webhook-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "queue_delivery": True,
                "delivery_channel": "email",
                "delivery_provider": "transactional_email",
            },
        )
        self.assertEqual(invite.status_code, 201, invite.text)
        invite_payload = invite.json()
        raw_token = invite_payload["token"]
        attempt_id = invite_payload["delivery_attempt"]["attempt_id"]
        self.assertEqual(invite_payload["delivery_attempt"]["status"], "queued")
        self.assertIsNone(invite_payload["delivered_at"])

        webhook_payload = {
            "provider": "transactional_email",
            "provider_event_id": "email-event-delivered-1",
            "attempt_id": attempt_id,
            "event_type": "delivered",
            "recipient": "delivery-webhook-analyst@example.com",
            "metadata": {"message_id": "message-1"},
        }
        webhook_body = json.dumps(
            webhook_payload,
            separators=(",", ":"),
        ).encode("utf-8")

        disabled = self.client.post(
            "/webhooks/staff-invite-delivery",
            content=webhook_body,
            headers={"content-type": "application/json"},
        )
        self.assertEqual(disabled.status_code, 503, disabled.text)

        with patch.dict(
            os.environ,
            {"MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET": "webhook-secret"},
            clear=False,
        ):
            unsigned = self.client.post(
                "/webhooks/staff-invite-delivery",
                content=webhook_body,
                headers={"content-type": "application/json"},
            )
            self.assertEqual(unsigned.status_code, 401, unsigned.text)

            delivered = self.client.post(
                "/webhooks/staff-invite-delivery",
                content=webhook_body,
                headers=self._webhook_headers(webhook_body),
            )
            self.assertEqual(delivered.status_code, 202, delivered.text)
            delivered_payload = delivered.json()
            self.assertEqual(delivered_payload["event_type"], "delivered")
            self.assertEqual(delivered_payload["mapped_attempt_status"], "sent")
            self.assertTrue(delivered_payload["delivery_recorded"])
            self.assertFalse(delivered_payload["was_duplicate"])
            self.assertNotIn("webhook-secret", json.dumps(delivered_payload))

            duplicate = self.client.post(
                "/webhooks/staff-invite-delivery",
                content=webhook_body,
                headers=self._webhook_headers(webhook_body),
            )
            self.assertEqual(duplicate.status_code, 202, duplicate.text)
            self.assertTrue(duplicate.json()["was_duplicate"])
            self.assertFalse(duplicate.json()["delivery_recorded"])

        listed_invites = self.client.get(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
        )
        self.assertEqual(listed_invites.status_code, 200, listed_invites.text)
        listed = next(
            row for row in listed_invites.json() if row["token_id"] == invite_payload["token_id"]
        )
        self.assertIsNotNone(listed["delivered_at"])
        self.assertIsNone(listed["delivered_by"])
        self.assertEqual(listed["last_delivery_status"], "sent")
        self.assertEqual(listed["delivery_event_count"], 1)
        self.assertEqual(listed["last_delivery_event_type"], "delivered")

        events = self.client.get(
            f"/admin/staff-invites/{invite_payload['token_id']}/delivery-events",
            headers=self._headers(admin_token),
        )
        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(len(events.json()), 1)
        self.assertEqual(events.json()[0]["provider_event_id"], "email-event-delivered-1")
        self.assertNotIn(raw_token, json.dumps(events.json()))

        failed_invite = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "delivery-webhook-bounced@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "queue_delivery": True,
                "delivery_channel": "email",
                "delivery_provider": "transactional_email",
            },
        )
        self.assertEqual(failed_invite.status_code, 201, failed_invite.text)
        failed_payload = {
            "provider": "transactional_email",
            "provider_event_id": "email-event-bounced-1",
            "attempt_id": failed_invite.json()["delivery_attempt"]["attempt_id"],
            "event_type": "bounced",
            "recipient": "delivery-webhook-bounced@example.com",
            "error": "Mailbox unavailable",
            "metadata": {"message_id": "message-2"},
        }
        failed_body = json.dumps(failed_payload, separators=(",", ":")).encode("utf-8")
        with patch.dict(
            os.environ,
            {"MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET": "webhook-secret"},
            clear=False,
        ):
            failed_webhook = self.client.post(
                "/webhooks/staff-invite-delivery",
                content=failed_body,
                headers=self._webhook_headers(failed_body),
            )
        self.assertEqual(failed_webhook.status_code, 202, failed_webhook.text)
        self.assertEqual(failed_webhook.json()["mapped_attempt_status"], "failed")
        self.assertFalse(failed_webhook.json()["delivery_recorded"])

        refreshed_failed = self.client.get(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
        )
        bounced = next(
            row
            for row in refreshed_failed.json()
            if row["token_id"] == failed_invite.json()["token_id"]
        )
        self.assertIsNone(bounced["delivered_at"])
        self.assertEqual(bounced["last_delivery_status"], "failed")
        self.assertEqual(bounced["last_delivery_event_type"], "bounced")

        audit = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        )
        serialized_audit = json.dumps(audit.json())
        self.assertIn("staff_invite_delivery_webhook_received", serialized_audit)
        self.assertNotIn(raw_token, serialized_audit)

    def test_staff_invite_delivery_outbox_worker_dead_letters_exhausted_attempts(self) -> None:
        admin_token = self._register("delivery-worker-admin@example.com", "admin")
        invite = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "delivery-worker-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "expires_in_hours": 72,
                "queue_delivery": True,
                "delivery_channel": "email",
                "delivery_recipient": "delivery-worker-analyst@example.com",
                "delivery_provider": "local_queue",
            },
        )
        self.assertEqual(invite.status_code, 201, invite.text)
        invite_payload = invite.json()
        attempt_id = invite_payload["delivery_attempt"]["attempt_id"]
        self.assertEqual(invite_payload["delivery_attempt"]["status"], "queued")
        self.assertEqual(invite_payload["delivery_attempt"]["worker_status"], "queued")
        self.assertEqual(invite_payload["delivery_attempt"]["worker_attempt_count"], 0)
        self.assertIsNotNone(invite_payload["delivery_attempt"]["next_worker_run_at"])

        outbox = self.client.get(
            "/admin/staff-invites/delivery-outbox",
            headers=self._headers(admin_token),
        )
        self.assertEqual(outbox.status_code, 200, outbox.text)
        self.assertEqual(outbox.json()["status"], "attention")
        self.assertEqual(outbox.json()["queued_count"], 1)
        self.assertEqual(outbox.json()["due_count"], 1)
        self.assertEqual(outbox.json()["dead_letter_count"], 0)
        self.assertIn("does not send messages", outbox.json()["limitation"])
        self.assertTrue(outbox.json()["items"][0]["due"])
        self.assertTrue(outbox.json()["items"][0]["invite_active_pending"])
        adapter_key = outbox.json()["items"][0]["adapter_idempotency_key"]
        self.assertGreaterEqual(len(adapter_key), 12)

        dry_run = self.client.post(
            "/admin/staff-invites/delivery-outbox/run",
            headers=self._headers(admin_token),
            json={"limit": 10, "max_attempts": 1, "backoff_seconds": 60, "dry_run": True},
        )
        self.assertEqual(dry_run.status_code, 200, dry_run.text)
        self.assertTrue(dry_run.json()["dry_run"])
        self.assertEqual(dry_run.json()["processed_count"], 1)
        self.assertEqual(dry_run.json()["results"][0]["action"], "dry_run")
        self.assertEqual(dry_run.json()["results"][0]["adapter_idempotency_key"], adapter_key)

        run = self.client.post(
            "/admin/staff-invites/delivery-outbox/run",
            headers=self._headers(admin_token),
            json={"limit": 10, "max_attempts": 1, "backoff_seconds": 60},
        )
        self.assertEqual(run.status_code, 200, run.text)
        run_payload = run.json()
        self.assertFalse(run_payload["dry_run"])
        self.assertEqual(run_payload["processed_count"], 1)
        self.assertEqual(run_payload["dead_lettered_count"], 1)
        self.assertEqual(run_payload["retry_scheduled_count"], 0)
        self.assertEqual(run_payload["results"][0]["action"], "dead_lettered")
        self.assertEqual(run_payload["results"][0]["worker_status"], "dead_letter")
        self.assertEqual(run_payload["results"][0]["worker_attempt_count"], 1)
        self.assertEqual(run_payload["results"][0]["adapter_idempotency_key"], adapter_key)
        self.assertIn("cannot send", run_payload["results"][0]["error"])

        attempts = self.client.get(
            f"/admin/staff-invites/{invite_payload['token_id']}/delivery-attempts",
            headers=self._headers(admin_token),
        )
        self.assertEqual(attempts.status_code, 200, attempts.text)
        stored_attempt = attempts.json()[0]
        self.assertEqual(stored_attempt["attempt_id"], attempt_id)
        self.assertEqual(stored_attempt["status"], "failed")
        self.assertEqual(stored_attempt["worker_status"], "dead_letter")
        self.assertEqual(stored_attempt["worker_attempt_count"], 1)
        self.assertIsNotNone(stored_attempt["dead_letter_at"])
        self.assertIsNone(stored_attempt["next_worker_run_at"])

        refreshed_outbox = self.client.get(
            "/admin/staff-invites/delivery-outbox",
            headers=self._headers(admin_token),
        )
        self.assertEqual(refreshed_outbox.status_code, 200, refreshed_outbox.text)
        self.assertEqual(refreshed_outbox.json()["dead_letter_count"], 1)
        self.assertEqual(refreshed_outbox.json()["due_count"], 0)

        audit = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        )
        self.assertEqual(audit.status_code, 200, audit.text)
        serialized_audit = json.dumps(audit.json())
        self.assertIn("staff_invite_delivery_worker_run", serialized_audit)
        self.assertIn("adapter_idempotency_keys", serialized_audit)
        self.assertNotIn(invite_payload["token"], serialized_audit)

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
        mfa_readiness = self.client.get(
            "/admin/security/mfa-readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(mfa_readiness.status_code, 200, mfa_readiness.text)
        self.assertEqual(mfa_readiness.json()["status"], "ready")
        self.assertEqual(mfa_readiness.json()["missing_mfa_count"], 0)
        self.assertIn("requires a second-factor code", mfa_readiness.json()["limitation"])

        repeated_mfa = self.client.post(
            "/admin/users/provisioning-admin@example.com/mfa/attest",
            headers=self._headers(admin_token),
            json={"method": "totp"},
        )
        self.assertEqual(repeated_mfa.status_code, 200, repeated_mfa.text)
        self.assertTrue(repeated_mfa.json()["was_already_attested"])
        self.assertEqual(repeated_mfa.json()["mfa_method"], "prototype_mfa_code")

        borrower_mfa = self.client.post(
            "/admin/users/regular@example.com/mfa/attest",
            headers=self._headers(admin_token),
            json={"method": "pilot_attestation"},
        )
        self.assertEqual(borrower_mfa.status_code, 409, borrower_mfa.text)

        mfa_readiness_after = self.client.get(
            "/admin/security/mfa-readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(mfa_readiness_after.status_code, 200, mfa_readiness_after.text)
        self.assertEqual(mfa_readiness_after.json()["status"], "ready")
        self.assertEqual(mfa_readiness_after.json()["mfa_attested_count"], 1)
        security_readiness = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(security_readiness.status_code, 200, security_readiness.text)
        self.assertEqual(security_readiness.json()["status"], "ready")
        security_checks = {
            check["key"]: check for check in security_readiness.json()["checks"]
        }
        self.assertEqual(security_checks["mfa_attestation"]["status"], "pass")
        self.assertEqual(security_checks["session_ttl"]["status"], "pass")
        self.assertEqual(security_checks["mfa_enforcement"]["status"], "pass")
        self.assertEqual(security_checks["mfa_challenge_failures"]["status"], "pass")
        self.assertEqual(security_checks["invite_delivery"]["status"], "pass")
        self.assertIn("not a completed production security review", security_readiness.json()["limitation"])

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

        missing_mfa_login = self.client.post(
            "/auth/login",
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(missing_mfa_login.status_code, 403, missing_mfa_login.text)
        self.assertIn("MFA attestation required", missing_mfa_login.json()["detail"])

        mfa_attested = self.client.post(
            "/admin/users/new-analyst@example.com/mfa/attest",
            headers=self._headers(admin_token),
            json={"method": "pilot_attestation"},
        )
        self.assertEqual(mfa_attested.status_code, 200, mfa_attested.text)
        self.assertEqual(mfa_attested.json()["email"], "new-analyst@example.com")
        self.assertIsNotNone(mfa_attested.json()["mfa_attested_at"])
        self.assertEqual(mfa_attested.json()["mfa_attested_by"], "provisioning-admin@example.com")
        self.assertEqual(mfa_attested.json()["mfa_method"], "pilot_attestation")
        self.assertFalse(mfa_attested.json()["was_already_attested"])

        invalid_mfa_login = self.client.post(
            "/auth/login",
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": "000000",
            },
        )
        self.assertEqual(invalid_mfa_login.status_code, 401, invalid_mfa_login.text)
        self.assertIn("Invalid MFA code", invalid_mfa_login.json()["detail"])

        mfa_failure_readiness = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(mfa_failure_readiness.status_code, 200, mfa_failure_readiness.text)
        mfa_failure_check = next(
            check for check in mfa_failure_readiness.json()["checks"]
            if check["key"] == "mfa_challenge_failures"
        )
        self.assertEqual(mfa_failure_check["status"], "warning")
        self.assertIn("failed staff MFA challenge", mfa_failure_check["summary"])

        analyst_login = self.client.post(
            "/auth/login",
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(analyst_login.status_code, 200, analyst_login.text)
        self.assertEqual(analyst_login.json()["role"], "mfi_analyst")
        analyst_token = analyst_login.json()["access_token"]

        staff_sessions = self.client.get(
            "/admin/staff-sessions",
            headers=self._headers(admin_token),
        )
        self.assertEqual(staff_sessions.status_code, 200, staff_sessions.text)
        session_rows = staff_sessions.json()
        self.assertGreaterEqual(len(session_rows), 2)
        self.assertTrue(all("token" not in row for row in session_rows))
        admin_session_row = next(
            row for row in session_rows
            if row["email"] == "provisioning-admin@example.com" and row["is_current_session"]
        )
        analyst_session_row = next(
            row for row in session_rows
            if row["email"] == "new-analyst@example.com" and not row["is_current_session"]
        )
        self.assertEqual(analyst_session_row["role"], "mfi_analyst")
        self.assertEqual(analyst_session_row["organization_id"], TEST_ORGANIZATION_ID)
        self.assertIn("session_expires_at", analyst_session_row)

        self_revoke = self.client.delete(
            f"/admin/staff-sessions/{admin_session_row['session_id']}",
            headers=self._headers(admin_token),
        )
        self.assertEqual(self_revoke.status_code, 409, self_revoke.text)

        revoked_staff_session = self.client.delete(
            f"/admin/staff-sessions/{analyst_session_row['session_id']}",
            headers=self._headers(admin_token),
        )
        self.assertEqual(revoked_staff_session.status_code, 200, revoked_staff_session.text)
        self.assertTrue(revoked_staff_session.json()["revoked"])
        self.assertEqual(revoked_staff_session.json()["email"], "new-analyst@example.com")
        self.assertEqual(revoked_staff_session.json()["role"], "mfi_analyst")
        revoked_analyst_session = self.client.get("/me", headers=self._headers(analyst_token))
        self.assertEqual(revoked_analyst_session.status_code, 401, revoked_analyst_session.text)
        repeated_session_revoke = self.client.delete(
            f"/admin/staff-sessions/{analyst_session_row['session_id']}",
            headers=self._headers(admin_token),
        )
        self.assertEqual(repeated_session_revoke.status_code, 404, repeated_session_revoke.text)

        analyst_login = self.client.post(
            "/auth/login",
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(analyst_login.status_code, 200, analyst_login.text)
        analyst_token = analyst_login.json()["access_token"]

        disabled = self.client.post(
            "/admin/users/new-analyst@example.com/disable",
            headers=self._headers(admin_token),
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertEqual(disabled.json()["email"], "new-analyst@example.com")
        self.assertIsNotNone(disabled.json()["disabled_at"])
        self.assertEqual(disabled.json()["disabled_by"], "provisioning-admin@example.com")
        self.assertEqual(disabled.json()["revoked_session_count"], 1)
        self.assertFalse(disabled.json()["was_already_disabled"])

        revoked_session = self.client.get("/me", headers=self._headers(analyst_token))
        self.assertEqual(revoked_session.status_code, 401, revoked_session.text)

        disabled_login = self.client.post(
            "/auth/login",
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(disabled_login.status_code, 403, disabled_login.text)

        repeated_disable = self.client.post(
            "/admin/users/new-analyst@example.com/disable",
            headers=self._headers(admin_token),
        )
        self.assertEqual(repeated_disable.status_code, 200, repeated_disable.text)
        self.assertTrue(repeated_disable.json()["was_already_disabled"])
        self.assertEqual(repeated_disable.json()["revoked_session_count"], 0)

        reactivated = self.client.post(
            "/admin/users/new-analyst@example.com/reactivate",
            headers=self._headers(admin_token),
        )
        self.assertEqual(reactivated.status_code, 200, reactivated.text)
        self.assertEqual(reactivated.json()["email"], "new-analyst@example.com")
        self.assertIsNone(reactivated.json()["disabled_at"])
        self.assertIsNone(reactivated.json()["disabled_by"])
        self.assertFalse(reactivated.json()["was_already_active"])

        reactivated_login = self.client.post(
            "/auth/login",
            json={
                "email": "new-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(reactivated_login.status_code, 200, reactivated_login.text)
        self.assertEqual(reactivated_login.json()["role"], "mfi_analyst")

        repeated_reactivation = self.client.post(
            "/admin/users/new-analyst@example.com/reactivate",
            headers=self._headers(admin_token),
        )
        self.assertEqual(repeated_reactivation.status_code, 200, repeated_reactivation.text)
        self.assertTrue(repeated_reactivation.json()["was_already_active"])

        borrower_disable = self.client.post(
            "/admin/users/regular@example.com/disable",
            headers=self._headers(admin_token),
        )
        self.assertEqual(borrower_disable.status_code, 409, borrower_disable.text)
        borrower_reactivation = self.client.post(
            "/admin/users/regular@example.com/reactivate",
            headers=self._headers(admin_token),
        )
        self.assertEqual(borrower_reactivation.status_code, 409, borrower_reactivation.text)

        invite = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "invited-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "expires_in_hours": 24,
            },
        )
        self.assertEqual(invite.status_code, 201, invite.text)
        invite_payload = invite.json()
        self.assertEqual(invite_payload["email"], "invited-analyst@example.com")
        self.assertEqual(invite_payload["role"], "mfi_analyst")
        self.assertEqual(invite_payload["organization_id"], TEST_ORGANIZATION_ID)
        self.assertIsNone(invite_payload["accepted_at"])
        self.assertIsNone(invite_payload["revoked_at"])
        self.assertIn("token", invite_payload)
        self.assertIn("invite_url", invite_payload)
        self.assertIn("token_id", invite_payload)
        self.assertIn("token_preview", invite_payload)
        self.assertNotEqual(invite_payload["token"], invite_payload["token_id"])
        self.assertIn(invite_payload["token"], invite_payload["invite_url"])
        self.assertNotIn(invite_payload["token_id"], invite_payload["invite_url"])
        self.assertEqual(len(invite_payload["token_id"]), 64)
        self.assertEqual(invite_payload["delivery_attempt_count"], 0)
        self.assertIsNone(invite_payload["delivery_attempt"])
        self.assertNotIn("password", invite_payload)

        undelivered_readiness = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(undelivered_readiness.status_code, 200, undelivered_readiness.text)
        undelivered_check = next(
            check for check in undelivered_readiness.json()["checks"]
            if check["key"] == "invite_delivery"
        )
        self.assertEqual(undelivered_check["status"], "blocker")

        delivered = self.client.post(
            f"/admin/staff-invites/{invite_payload['token_id']}/delivery",
            headers=self._headers(admin_token),
            json={"channel": "manual_copy"},
        )
        self.assertEqual(delivered.status_code, 200, delivered.text)
        self.assertEqual(delivered.json()["email"], "invited-analyst@example.com")
        self.assertIsNotNone(delivered.json()["delivered_at"])
        self.assertEqual(delivered.json()["delivered_by"], "provisioning-admin@example.com")
        self.assertEqual(delivered.json()["delivery_channel"], "manual_copy")
        self.assertEqual(delivered.json()["delivery_url_base"], "http://127.0.0.1:5173")
        self.assertEqual(delivered.json()["delivery_attempt_count"], 1)
        self.assertEqual(delivered.json()["last_delivery_status"], "sent")
        self.assertEqual(delivered.json()["last_delivery_provider"], "manual_receipt")
        self.assertEqual(delivered.json()["delivery_attempt"]["provider"], "manual_receipt")
        self.assertEqual(delivered.json()["delivery_attempt"]["status"], "sent")
        self.assertEqual(delivered.json()["delivery_attempt"]["channel"], "manual_copy")
        self.assertNotIn(invite_payload["token"], delivered.json()["delivery_attempt"].values())
        self.assertFalse(delivered.json()["was_already_delivered"])

        repeated_delivery = self.client.post(
            f"/admin/staff-invites/{invite_payload['token_id']}/delivery",
            headers=self._headers(admin_token),
            json={"channel": "manual_copy"},
        )
        self.assertEqual(repeated_delivery.status_code, 200, repeated_delivery.text)
        self.assertTrue(repeated_delivery.json()["was_already_delivered"])
        self.assertEqual(repeated_delivery.json()["delivery_attempt_count"], 2)
        delivery_attempts = self.client.get(
            f"/admin/staff-invites/{invite_payload['token_id']}/delivery-attempts",
            headers=self._headers(admin_token),
        )
        self.assertEqual(delivery_attempts.status_code, 200, delivery_attempts.text)
        self.assertEqual(len(delivery_attempts.json()), 2)
        self.assertTrue(
            all(attempt["provider"] == "manual_receipt" for attempt in delivery_attempts.json())
        )
        self.assertTrue(
            all(invite_payload["token"] not in attempt.values() for attempt in delivery_attempts.json())
        )

        delivered_readiness = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(delivered_readiness.status_code, 200, delivered_readiness.text)
        delivered_check = next(
            check for check in delivered_readiness.json()["checks"]
            if check["key"] == "invite_delivery"
        )
        self.assertEqual(delivered_check["status"], "pass")

        failed_delivery_invite = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "failed-delivery-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "expires_in_hours": 72,
                "queue_delivery": True,
                "delivery_channel": "email",
                "delivery_recipient": "failed-delivery-analyst@example.com",
                "delivery_provider": "local_fail",
            },
        )
        self.assertEqual(failed_delivery_invite.status_code, 201, failed_delivery_invite.text)
        failed_payload = failed_delivery_invite.json()
        self.assertIsNone(failed_payload["delivered_at"])
        self.assertEqual(failed_payload["delivery_attempt_count"], 1)
        self.assertEqual(failed_payload["last_delivery_status"], "failed")
        self.assertEqual(failed_payload["last_delivery_provider"], "local_fail")
        self.assertEqual(failed_payload["delivery_attempt"]["status"], "failed")
        self.assertEqual(failed_payload["delivery_attempt"]["provider"], "local_fail")
        self.assertIn("simulated failure", failed_payload["delivery_attempt"]["error"])

        failed_readiness = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(failed_readiness.status_code, 200, failed_readiness.text)
        failed_delivery_check = next(
            check for check in failed_readiness.json()["checks"]
            if check["key"] == "invite_delivery"
        )
        failed_attempt_check = next(
            check for check in failed_readiness.json()["checks"]
            if check["key"] == "invite_delivery_attempts"
        )
        self.assertEqual(failed_delivery_check["status"], "blocker")
        self.assertEqual(failed_attempt_check["status"], "warning")

        retry_delivery = self.client.post(
            f"/admin/staff-invites/{failed_payload['token_id']}/delivery-attempts/retry",
            headers=self._headers(admin_token),
            json={"channel": "email", "provider": "local_outbox"},
        )
        self.assertEqual(retry_delivery.status_code, 200, retry_delivery.text)
        retry_payload = retry_delivery.json()
        self.assertIsNotNone(retry_payload["delivered_at"])
        self.assertFalse(retry_payload["was_already_delivered"])
        self.assertEqual(retry_payload["delivery_attempt_count"], 2)
        self.assertEqual(retry_payload["last_delivery_status"], "sent")
        self.assertEqual(retry_payload["last_delivery_provider"], "local_outbox")
        self.assertEqual(retry_payload["delivery_attempt"]["status"], "sent")
        self.assertEqual(retry_payload["delivery_attempt"]["provider"], "local_outbox")

        failed_retry_attempts = self.client.get(
            f"/admin/staff-invites/{failed_payload['token_id']}/delivery-attempts",
            headers=self._headers(admin_token),
        )
        self.assertEqual(failed_retry_attempts.status_code, 200, failed_retry_attempts.text)
        self.assertEqual(len(failed_retry_attempts.json()), 2)
        self.assertEqual(
            [attempt["status"] for attempt in failed_retry_attempts.json()],
            ["sent", "failed"],
        )
        self.assertTrue(
            all(
                failed_payload["token"] not in attempt.values()
                for attempt in failed_retry_attempts.json()
            )
        )

        retried_readiness = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(retried_readiness.status_code, 200, retried_readiness.text)
        retried_delivery_check = next(
            check for check in retried_readiness.json()["checks"]
            if check["key"] == "invite_delivery"
        )
        retried_attempt_check = next(
            check for check in retried_readiness.json()["checks"]
            if check["key"] == "invite_delivery_attempts"
        )
        self.assertEqual(retried_delivery_check["status"], "pass")
        self.assertEqual(retried_attempt_check["status"], "pass")

        weak_accept = self.client.post(
            "/auth/accept-staff-invite",
            json={"token": invite_payload["token"], "password": "password123"},
        )
        self.assertEqual(weak_accept.status_code, 422, weak_accept.text)

        invalid_invite_mfa = self.client.post(
            "/auth/accept-staff-invite",
            json={
                "token": invite_payload["token"],
                "password": TEST_PASSWORD,
                "mfa_code": "000000",
            },
        )
        self.assertEqual(invalid_invite_mfa.status_code, 401, invalid_invite_mfa.text)
        self.assertIn("Invalid MFA code", invalid_invite_mfa.json()["detail"])

        accepted = self.client.post(
            "/auth/accept-staff-invite",
            json={
                "token": invite_payload["token"],
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["role"], "mfi_analyst")
        self.assertEqual(accepted.json()["organization_id"], TEST_ORGANIZATION_ID)
        self.assertIn("session_expires_at", accepted.json())
        self.assertEqual(accepted.json()["session_ttl_seconds"], 8 * 60 * 60)

        reused = self.client.post(
            "/auth/accept-staff-invite",
            json={
                "token": invite_payload["token"],
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
        )
        self.assertEqual(reused.status_code, 409, reused.text)

        accepted_revoke = self.client.delete(
            f"/admin/staff-invites/{invite_payload['token_id']}",
            headers=self._headers(admin_token),
        )
        self.assertEqual(accepted_revoke.status_code, 409, accepted_revoke.text)

        accepted_rotate = self.client.post(
            f"/admin/staff-invites/{invite_payload['token_id']}/rotate",
            headers=self._headers(admin_token),
            json={"expires_in_hours": 24},
        )
        self.assertEqual(accepted_rotate.status_code, 409, accepted_rotate.text)

        invites = self.client.get(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
        )
        self.assertEqual(invites.status_code, 200, invites.text)
        self.assertTrue(all("token" not in row for row in invites.json()))
        self.assertTrue(
            any(
                row["email"] == "invited-analyst@example.com"
                and row["token_id"] == invite_payload["token_id"]
                and row["token_preview"] == invite_payload["token_preview"]
                and row["accepted_at"]
                and row["accepted_by"] == "invited-analyst@example.com"
                and row["delivered_at"]
                and row["delivery_attempt_count"] == 2
                for row in invites.json()
            )
        )

        rotate_source = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "rotated-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "expires_in_hours": 24,
            },
        )
        self.assertEqual(rotate_source.status_code, 201, rotate_source.text)
        rotate_source_payload = rotate_source.json()
        rotated = self.client.post(
            f"/admin/staff-invites/{rotate_source_payload['token_id']}/rotate",
            headers=self._headers(admin_token),
            json={
                "expires_in_hours": 72,
                "queue_delivery": True,
                "delivery_channel": "email",
                "delivery_recipient": "rotated-analyst@example.com",
            },
        )
        self.assertEqual(rotated.status_code, 201, rotated.text)
        rotated_payload = rotated.json()
        self.assertEqual(rotated_payload["email"], "rotated-analyst@example.com")
        self.assertNotEqual(rotated_payload["token_id"], rotate_source_payload["token_id"])
        self.assertNotEqual(rotated_payload["token"], rotate_source_payload["token"])
        self.assertIn(rotated_payload["token"], rotated_payload["invite_url"])
        self.assertNotIn(rotate_source_payload["token"], rotated_payload["invite_url"])
        self.assertNotIn(rotate_source_payload["token_id"], rotated_payload["invite_url"])
        self.assertIsNone(rotated_payload["revoked_at"])
        self.assertIsNotNone(rotated_payload["delivered_at"])
        self.assertEqual(rotated_payload["delivery_attempt_count"], 1)
        self.assertEqual(rotated_payload["delivery_attempt"]["provider"], "local_outbox")
        self.assertEqual(rotated_payload["delivery_attempt"]["channel"], "email")
        self.assertNotIn(rotate_source_payload["token"], rotated_payload["delivery_attempt"].values())
        old_rotated_accept = self.client.post(
            "/auth/accept-staff-invite",
            json={"token": rotate_source_payload["token"], "password": TEST_PASSWORD},
        )
        self.assertEqual(old_rotated_accept.status_code, 410, old_rotated_accept.text)
        rotated_invites = self.client.get(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
        )
        self.assertEqual(rotated_invites.status_code, 200, rotated_invites.text)
        old_rotated_row = next(
            row for row in rotated_invites.json()
            if row["token_id"] == rotate_source_payload["token_id"]
        )
        self.assertIsNotNone(old_rotated_row["revoked_at"])
        self.assertEqual(old_rotated_row["revoked_by"], "provisioning-admin@example.com")
        new_rotated_row = next(
            row for row in rotated_invites.json()
            if row["token_id"] == rotated_payload["token_id"]
        )
        self.assertIsNotNone(new_rotated_row["delivered_at"])
        self.assertEqual(new_rotated_row["delivery_attempt_count"], 1)
        self.assertEqual(new_rotated_row["last_delivery_provider"], "local_outbox")
        self.assertNotIn("token", new_rotated_row)
        repeated_rotation = self.client.post(
            f"/admin/staff-invites/{rotate_source_payload['token_id']}/rotate",
            headers=self._headers(admin_token),
            json={"expires_in_hours": 72},
        )
        self.assertEqual(repeated_rotation.status_code, 409, repeated_rotation.text)
        self.assertIn("Active staff invite already exists", repeated_rotation.json()["detail"])

        revokable = self.client.post(
            "/admin/staff-invites",
            headers=self._headers(admin_token),
            json={
                "email": "revoked-analyst@example.com",
                "role": "mfi_analyst",
                "organization_id": TEST_ORGANIZATION_ID,
                "expires_in_hours": 24,
            },
        )
        self.assertEqual(revokable.status_code, 201, revokable.text)
        revoked = self.client.delete(
            f"/admin/staff-invites/{revokable.json()['token_id']}",
            headers=self._headers(admin_token),
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertIsNotNone(revoked.json()["revoked_at"])
        self.assertEqual(revoked.json()["revoked_by"], "provisioning-admin@example.com")

        repeated_revoke = self.client.delete(
            f"/admin/staff-invites/{revokable.json()['token_id']}",
            headers=self._headers(admin_token),
        )
        self.assertEqual(repeated_revoke.status_code, 200, repeated_revoke.text)
        self.assertEqual(repeated_revoke.json()["revoked_at"], revoked.json()["revoked_at"])

        revoked_accept = self.client.post(
            "/auth/accept-staff-invite",
            json={"token": revokable.json()["token"], "password": TEST_PASSWORD},
        )
        self.assertEqual(revoked_accept.status_code, 410, revoked_accept.text)

        self.repository.create_staff_invite(
            token="expired-staff-invite-token",
            email="expired-analyst@example.com",
            role="mfi_analyst",
            organization_id=TEST_ORGANIZATION_ID,
            created_by="provisioning-admin@example.com",
            expires_at="2020-01-01T00:00:00+00:00",
        )
        expired = self.client.post(
            "/auth/accept-staff-invite",
            json={"token": "expired-staff-invite-token", "password": TEST_PASSWORD},
        )
        self.assertEqual(expired.status_code, 410, expired.text)
        invite_health = self.client.get(
            "/admin/staff-invites/health",
            headers=self._headers(admin_token),
        )
        self.assertEqual(invite_health.status_code, 200, invite_health.text)
        self.assertEqual(invite_health.json()["status"], "attention")
        self.assertEqual(invite_health.json()["expired_pending_count"], 1)
        self.assertEqual(invite_health.json()["action_required_count"], 1)
        self.assertEqual(invite_health.json()["window_hours"], 24)
        self.assertIn("Review expired", invite_health.json()["recommended_action"])
        security_after_expired_invite = self.client.get(
            "/admin/security/readiness",
            headers=self._headers(admin_token),
        )
        self.assertEqual(security_after_expired_invite.status_code, 200, security_after_expired_invite.text)
        invite_check = next(
            check for check in security_after_expired_invite.json()["checks"]
            if check["key"] == "invite_hygiene"
        )
        self.assertEqual(invite_check["status"], "blocker")

        audit = self.client.get(
            "/admin/audit-events",
            headers=self._headers(admin_token),
        ).json()
        provisioning_event = next(
            event for event in audit if event["action"] == "staff_user_created"
        )
        self.assertEqual(provisioning_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(provisioning_event["entity_id"], "new-analyst@example.com")
        mfa_attested_event = next(
            event
            for event in audit
            if event["action"] == "staff_mfa_attested"
            and event["entity_id"] == "new-analyst@example.com"
        )
        self.assertEqual(mfa_attested_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(mfa_attested_event["entity_id"], "new-analyst@example.com")
        self.assertEqual(mfa_attested_event["details"]["method"], "pilot_attestation")
        mfa_login_event = next(
            event
            for event in audit
            if event["action"] == "staff_mfa_login_verified"
            and event["entity_id"] == "new-analyst@example.com"
        )
        self.assertTrue(mfa_login_event["details"]["prototype"])
        mfa_failure_events = [
            event for event in audit if event["action"] == "staff_mfa_challenge_failed"
        ]
        self.assertGreaterEqual(len(mfa_failure_events), 3)
        mfa_failure_reasons = {event["details"]["reason"] for event in mfa_failure_events}
        self.assertIn("missing_attestation", mfa_failure_reasons)
        self.assertIn("invalid_code", mfa_failure_reasons)
        self.assertIn(
            "staff_invite_acceptance",
            {event["details"]["source"] for event in mfa_failure_events},
        )
        self.assertTrue(
            all(
                "000000" not in event["details"].values()
                and invite_payload["token"] not in event["details"].values()
                for event in mfa_failure_events
            )
        )
        invite_created_event = next(
            event
            for event in audit
            if event["action"] == "staff_invite_created"
            and event["details"]["email"] == "invited-analyst@example.com"
        )
        self.assertEqual(invite_created_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(invite_created_event["entity_id"], invite_payload["token_id"])
        self.assertNotEqual(invite_created_event["entity_id"], invite_payload["token"])
        self.assertEqual(invite_created_event["details"]["email"], "invited-analyst@example.com")
        self.assertEqual(invite_created_event["details"]["token_preview"], invite_payload["token_preview"])
        invite_delivered_event = next(
            event
            for event in audit
            if event["action"] == "staff_invite_delivered"
            and event["entity_id"] == invite_payload["token_id"]
        )
        self.assertEqual(invite_delivered_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(invite_delivered_event["entity_id"], invite_payload["token_id"])
        self.assertEqual(invite_delivered_event["details"]["delivery_channel"], "manual_copy")
        self.assertEqual(invite_delivered_event["details"]["delivery_url_base"], "http://127.0.0.1:5173")
        self.assertIn("delivery_attempt_id", invite_delivered_event["details"])
        self.assertNotIn(invite_payload["token"], invite_delivered_event["details"].values())
        delivery_attempt_events = [
            event for event in audit if event["action"] == "staff_invite_delivery_attempted"
        ]
        self.assertGreaterEqual(len(delivery_attempt_events), 5)
        self.assertIn(
            "manual_receipt",
            {event["details"]["provider"] for event in delivery_attempt_events},
        )
        self.assertIn(
            "local_outbox",
            {event["details"]["provider"] for event in delivery_attempt_events},
        )
        self.assertIn(
            "local_fail",
            {event["details"]["provider"] for event in delivery_attempt_events},
        )
        self.assertTrue(
            all(
                invite_payload["token"] not in event["details"].values()
                and failed_payload["token"] not in event["details"].values()
                for event in delivery_attempt_events
            )
        )
        invite_rotated_event = next(
            event for event in audit if event["action"] == "staff_invite_rotated"
        )
        self.assertEqual(invite_rotated_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(invite_rotated_event["entity_id"], rotated_payload["token_id"])
        self.assertEqual(invite_rotated_event["details"]["previous_status"], "pending")
        self.assertEqual(
            invite_rotated_event["details"]["previous_token_preview"],
            rotate_source_payload["token_preview"],
        )
        self.assertEqual(
            invite_rotated_event["details"]["new_token_preview"],
            rotated_payload["token_preview"],
        )
        self.assertNotIn(rotate_source_payload["token"], invite_rotated_event["details"].values())
        invite_accepted_event = next(
            event for event in audit if event["action"] == "staff_invite_accepted"
        )
        self.assertEqual(invite_accepted_event["actor_email"], "invited-analyst@example.com")
        self.assertEqual(invite_accepted_event["entity_id"], invite_payload["token_id"])
        invite_revoked_event = next(
            event for event in audit if event["action"] == "staff_invite_revoked"
        )
        self.assertEqual(invite_revoked_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(invite_revoked_event["details"]["email"], "revoked-analyst@example.com")
        self.assertEqual(invite_revoked_event["entity_id"], revokable.json()["token_id"])
        staff_disabled_event = next(
            event for event in audit if event["action"] == "staff_user_disabled"
        )
        self.assertEqual(staff_disabled_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(staff_disabled_event["entity_id"], "new-analyst@example.com")
        self.assertEqual(staff_disabled_event["details"]["revoked_session_count"], 1)
        staff_session_revoked_event = next(
            event for event in audit if event["action"] == "staff_session_revoked"
        )
        self.assertEqual(staff_session_revoked_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(staff_session_revoked_event["entity_id"], analyst_session_row["session_id"])
        self.assertEqual(staff_session_revoked_event["details"]["email"], "new-analyst@example.com")
        self.assertIn("session_preview", staff_session_revoked_event["details"])
        self.assertNotIn(analyst_token, staff_session_revoked_event["details"].values())
        staff_reactivated_event = next(
            event for event in audit if event["action"] == "staff_user_reactivated"
        )
        self.assertEqual(staff_reactivated_event["actor_email"], "provisioning-admin@example.com")
        self.assertEqual(staff_reactivated_event["entity_id"], "new-analyst@example.com")
        self.assertEqual(
            staff_reactivated_event["details"]["previous_disabled_by"],
            "provisioning-admin@example.com",
        )

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
        self.repository.attest_user_mfa(
            "analyst-b@example.com",
            "analyst-b@example.com",
            "prototype_mfa_code",
        )
        analyst_b_login = self.client.post(
            "/auth/login",
            json={
                "email": "analyst-b@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
            },
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
        self.repository.attest_user_mfa(
            "simulation-other-analyst@example.com",
            "simulation-other-analyst@example.com",
            "prototype_mfa_code",
        )
        other_login = self.client.post(
            "/auth/login",
            json={
                "email": "simulation-other-analyst@example.com",
                "password": TEST_PASSWORD,
                "mfa_code": TEST_MFA_CODE,
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
                "behavioral_signals": {},
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
