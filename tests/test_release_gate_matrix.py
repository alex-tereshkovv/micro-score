from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"


MATRIX_ROWS = [
    {
        "area": "Auth/session expiry and logout",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "session_expires_at",
            "session_ttl_seconds",
            "/auth/logout",
            "session_expiry_visible",
            "logout_guard",
        ],
    },
    {
        "area": "Staff invites and delivery hygiene",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "/admin/staff-invites",
            "/auth/accept-staff-invite",
            "staff_invite_delivery_attempted",
            "staff_invite_rotated",
            "staff_invite_token_hygiene",
        ],
    },
    {
        "area": "MFA enforcement and readiness",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "/admin/security/mfa-readiness",
            "staff_mfa_attested",
            "staff_mfa_login_verified",
            "staff_mfa_challenge_failed",
            "mfa_readiness",
        ],
    },
    {
        "area": "Staff sessions and lifecycle controls",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "/admin/staff-sessions",
            "staff_session_revoked",
            "staff_user_disabled",
            "staff_user_reactivated",
            "staff_session_control",
        ],
    },
    {
        "area": "Tenant isolation",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_research_docs.py",
        ],
        "markers": [
            "organization_id",
            "cross-tenant detail access returns",
            "tenant_isolation",
            "/admin/organizations",
        ],
    },
    {
        "area": "Borrower lifecycle and borrower-safe projection",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "scripts/frontend-workflow-smoke.js",
            "tests/test_research_docs.py",
        ],
        "markers": [
            "BorrowerApplicationResponse",
            "borrower-safe",
            "lifecycle_terminal_guard",
            "terminal_locked",
            "score_result",
        ],
    },
    {
        "area": "Review action plan and risk detail readiness",
        "artifacts": [
            "tests/test_api_integration.py",
            "scripts/static-demo-smoke.js",
            "scripts/frontend-workflow-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "buildReviewActionPlan",
            "score_first",
            "review_or_decide",
            "finalize_decision",
            "action_plan_terminal",
        ],
    },
    {
        "area": "Monte Carlo portfolio simulation",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "tests/test_api_simulation.py",
            "scripts/static-demo-smoke.js",
            "tests/test_research_docs.py",
        ],
        "markers": [
            "portfolio_fingerprint",
            "calibration_volatility",
            "Monte Carlo standard errors",
            "simulation_history",
            "portfolio_simulation_run",
        ],
    },
    {
        "area": "Model registry and stale-score governance",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_research_docs.py",
        ],
        "markers": [
            "/admin/model-versions",
            "stale_model_version",
            "model_registry",
            "active_model",
            "immutable governance snapshot",
        ],
    },
    {
        "area": "Pre-pilot release readiness gate",
        "artifacts": [
            "tests/test_api_integration.py",
            "scripts/static-demo-smoke.js",
            "scripts/live-security-workflow-smoke.py",
            "tests/test_web_static.py",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "markers": [
            "/admin/governance/pre-pilot-readiness",
            "PrePilotReadinessResponse",
            "production_data_allowed",
            "public_demo_allowed",
            "pre_pilot_readiness_gate",
        ],
    },
    {
        "area": "Privacy intake and sensitive-field rejection",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_privacy.py",
            "scripts/application-intake-smoke.js",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "consent_confirmed",
            "borrower_consent",
            "find_forbidden_signal_paths",
            "privacy_guards",
            "Unexpected behavioral field",
        ],
    },
    {
        "area": "Research documentation boundaries",
        "artifacts": [
            "tests/test_research_docs.py",
            "tests/test_reporting.py",
            "tests/test_modeling.py",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "markers": [
            "synthetic data is not real-world lending",
            "Model Card and Data Statement",
            "calibration volatility",
            "Monte Carlo portfolio simulation",
            "research_governance_docs_exist",
        ],
    },
]


SECURITY_MATRIX_ROWS = [
    {
        "area": "Production identity readiness is explicit, not complete",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_research_docs.py",
            "scripts/static-demo-smoke.js",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "markers": [
            "not a completed production security review",
            "production IdP/TOTP/WebAuthn remains future work",
            "/admin/security/readiness",
            "security_readiness",
        ],
    },
    {
        "area": "Invite delivery mode is audited and local-only by default",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "markers": [
            "/admin/staff-invites/delivery-readiness",
            "/admin/staff-invites/delivery-adapter-readiness",
            "/admin/staff-invites/delivery-outbox",
            "/admin/staff-invites/delivery-outbox/run",
            "/webhooks/staff-invite-delivery",
            "staff_invite_delivery_webhook_received",
            "staff_invite_delivery_worker_run",
            "delivery_provider_not_production_ready",
            "delivery_provider_configuration_missing",
            "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY",
            "transactional_email_contract",
            "external_send_adapter_disabled",
            "adapter_idempotency_key",
            "dead_letter",
            "local_outbox",
            "staff_invite_delivery_retry",
        ],
    },
    {
        "area": "MFA and staff-session lifecycle are proven end to end",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
        ],
        "markers": [
            "staff_mfa_login_verified",
            "staff_mfa_challenge_failed",
            "/admin/staff-sessions",
            "staff_session_revoked",
            "staff_user_disabled",
        ],
    },
    {
        "area": "Storage assumptions remain visible before pilot use",
        "artifacts": [
            "tests/test_api_integration.py",
            "tests/test_api_database.py",
            "scripts/live-api-workflow-smoke.py",
            "scripts/live-security-workflow-smoke.py",
            "scripts/postgresql-migration-smoke.py",
            "scripts/static-demo-smoke.js",
            "tests/test_web_static.py",
            "tests/test_postgres_repository_adapter.py",
            ".github/workflows/ci.yml",
            "migrations/postgresql/0001_initial_schema.sql",
            "src/microscore_api/postgres_repository.py",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "markers": [
            "/admin/storage/postgresql-readiness",
            "PostgresMigrationReadinessResponse",
            "storage_readiness",
            "postgresql_schema_inventory",
            "postgresql_versioned_migration_artifacts",
            "postgresql_disposable_migration_ci",
            "disposable_migration_ci_present",
            "postgresql_repository_adapter_contract",
            "postgresql-repository-adapter-v8",
            "partial_method_groups",
            "model_registry_audit_organizations_identity_invites_applications_groups_v1",
            "postgresql_model_registry_read_adapter",
            "postgresql_model_registry_method_group_adapter",
            "postgresql_audit_method_group_adapter",
            "postgresql_organization_method_group_adapter",
            "postgresql_identity_access_method_group_adapter",
            "postgresql_staff_invites_delivery_method_group_adapter",
            "postgresql_application_lifecycle_method_group_adapter",
            "repository_adapter_contract_method_count",
            "repository_adapter_implemented_method_count",
            "repository_adapter_completed_method_group_count",
            "repository_adapter_audit_group_present",
            "repository_adapter_organization_group_present",
            "repository_adapter_identity_access_group_present",
            "repository_adapter_staff_invites_delivery_group_present",
            "repository_adapter_application_lifecycle_group_present",
            "0001_initial_schema",
            "migration_artifact_count",
            "postgres:16",
            "postgresql_disposable_ci",
            "MICROSCORE_STORAGE_BACKEND",
            "production_ready",
            "temporary-sqlite",
            "PostgreSQL",
        ],
    },
    {
        "area": "Live security workflow stays inside the release gate",
        "artifacts": [
            "scripts/check.ps1",
            "scripts/live-api-workflow-smoke.py",
            "scripts/live-security-workflow-smoke.py",
            "tests/test_github_workflows.py",
            "docs/RELEASE_CHECKLIST.md",
        ],
        "markers": [
            "Live API workflow smoke test",
            "Live security workflow smoke test",
            "scripts\\live-security-workflow-smoke.py",
            "temporary-sqlite",
            "session_preview",
            "token_preview",
        ],
    },
    {
        "area": "No-overclaim limitations remain release blockers",
        "artifacts": [
            "tests/test_research_docs.py",
            "docs/RELEASE_CHECKLIST.md",
            "docs/ENGINEERING_QUALITY.md",
        ],
        "markers": [
            "synthetic data is not real-world lending",
            "No real borrower",
            "production IdP/TOTP/WebAuthn remains future work",
            "SQLite",
            "not ready for real loan approval",
        ],
    },
]


class ReleaseGateMatrixTests(unittest.TestCase):
    def test_release_gate_matrix_references_real_artifacts_and_markers(self) -> None:
        matrix = (DOCS_ROOT / "ENGINEERING_QUALITY.md").read_text(encoding="utf-8")
        self.assertIn("Release Gate Matrix v1", matrix)
        self.assertIn("tests/test_release_gate_matrix.py", matrix)

        for row in MATRIX_ROWS:
            with self.subTest(area=row["area"]):
                self.assertIn(row["area"], matrix)

                artifact_text = ""
                for relative_path in row["artifacts"]:
                    path = PROJECT_ROOT / relative_path
                    self.assertTrue(path.exists(), relative_path)
                    self.assertIn(relative_path, matrix)
                    artifact_text += path.read_text(encoding="utf-8") + "\n"

                for marker in row["markers"]:
                    self.assertIn(marker, matrix)
                    self.assertIn(marker, artifact_text)

    def test_security_readiness_gate_matrix_references_real_security_proofs(self) -> None:
        matrix = (DOCS_ROOT / "ENGINEERING_QUALITY.md").read_text(encoding="utf-8")
        self.assertIn("Security Readiness Gate Matrix v1", matrix)

        for row in SECURITY_MATRIX_ROWS:
            with self.subTest(area=row["area"]):
                self.assertIn(row["area"], matrix)

                artifact_text = ""
                for relative_path in row["artifacts"]:
                    path = PROJECT_ROOT / relative_path
                    self.assertTrue(path.exists(), relative_path)
                    self.assertIn(relative_path, matrix)
                    artifact_text += path.read_text(encoding="utf-8") + "\n"

                for marker in row["markers"]:
                    self.assertIn(marker, matrix)
                    self.assertIn(marker, artifact_text)

    def test_release_checklist_points_to_matrix_drift_test(self) -> None:
        checklist = (DOCS_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

        self.assertIn("Release Gate Traceability", checklist)
        self.assertIn("Release Gate Matrix v1", checklist)
        self.assertIn("Security Readiness Gate Matrix v1", checklist)
        self.assertIn("tests.test_release_gate_matrix", checklist)

    def test_release_checklist_tracks_security_smokes_from_check_script(self) -> None:
        checklist = (DOCS_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        check_script = (PROJECT_ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

        required_smokes = [
            "scripts\\static-demo-smoke.js",
            "scripts\\frontend-workflow-smoke.js",
            "scripts\\postgresql-migration-smoke.py",
            "scripts\\live-api-workflow-smoke.py",
            "scripts\\live-security-workflow-smoke.py",
        ]
        for smoke in required_smokes:
            with self.subTest(smoke=smoke):
                self.assertIn(smoke, check_script)
                self.assertIn(smoke, checklist)

        for marker in [
            "PostgreSQL migration smoke dry run",
            "Live API workflow smoke test",
            "Live security workflow smoke test",
            "Security Readiness Gate Matrix v1",
            "production IdP/TOTP/WebAuthn remains future work",
            "SQLite is the prototype backend",
        ]:
            self.assertIn(marker, checklist)

    def test_github_workflow_test_pins_live_security_smoke_markers(self) -> None:
        workflow_test = (PROJECT_ROOT / "tests" / "test_github_workflows.py").read_text(
            encoding="utf-8",
        )

        for marker in [
            "live-api-workflow-smoke.py",
            "live-security-workflow-smoke.py",
            "Live API workflow smoke test",
            "Live security workflow smoke test",
            "security_readiness",
            "mfa_challenge_monitoring",
            "staff_invite_delivery_retry",
            "staff_invite_delivery_worker",
            "staff_invite_delivery_adapter_boundary",
            "/admin/staff-invites/delivery-outbox/run",
        ]:
            self.assertIn(marker, workflow_test)

    def test_windows_release_gate_still_runs_matrix_proofs(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

        for marker in [
            "unittest discover -s tests",
            "scripts\\application-intake-smoke.js",
            "scripts\\portfolio-dashboard-smoke.js",
            "scripts\\static-demo-smoke.js",
            "scripts\\frontend-workflow-smoke.js",
            "scripts\\postgresql-migration-smoke.py",
            "PostgreSQL migration smoke dry run",
            "scripts\\live-api-workflow-smoke.py",
            "Live API workflow smoke test",
            "scripts\\live-security-workflow-smoke.py",
            "Live security workflow smoke test",
            "git diff --check",
        ]:
            self.assertIn(marker, script)


if __name__ == "__main__":
    unittest.main()
