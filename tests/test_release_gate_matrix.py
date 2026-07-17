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

    def test_release_checklist_points_to_matrix_drift_test(self) -> None:
        checklist = (DOCS_ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

        self.assertIn("Release Gate Traceability", checklist)
        self.assertIn("Release Gate Matrix v1", checklist)
        self.assertIn("tests.test_release_gate_matrix", checklist)

    def test_windows_release_gate_still_runs_matrix_proofs(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

        for marker in [
            "unittest discover -s tests",
            "scripts\\application-intake-smoke.js",
            "scripts\\portfolio-dashboard-smoke.js",
            "scripts\\static-demo-smoke.js",
            "scripts\\frontend-workflow-smoke.js",
            "git diff --check",
        ]:
            self.assertIn(marker, script)


if __name__ == "__main__":
    unittest.main()
