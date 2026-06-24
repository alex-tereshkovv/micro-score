from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_ROOT = PROJECT_ROOT / ".github" / "workflows"


class GithubWorkflowTests(unittest.TestCase):
    def test_ci_workflow_runs_project_quality_gate(self) -> None:
        workflow = (WORKFLOWS_ROOT / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("actions/checkout@v6", workflow)
        self.assertIn("actions/setup-python@v6", workflow)
        self.assertIn('python-version: "3.12"', workflow)
        self.assertIn("actions/setup-node@v6", workflow)
        self.assertIn("node-version: 24", workflow)
        self.assertIn("python -m pip install -r requirements.txt", workflow)
        self.assertIn("python -m unittest discover -s tests", workflow)
        self.assertIn("python -m compileall", workflow)
        self.assertIn("python src/train_model.py", workflow)
        self.assertIn("python -m microscore --regional --decision", workflow)
        self.assertIn("node --check apps/web/app.js", workflow)
        self.assertIn("node --check apps/web/mock-api.js", workflow)
        self.assertIn("node --check apps/web/application-intake.js", workflow)
        self.assertIn("node --check apps/web/portfolio-dashboard.js", workflow)
        self.assertIn("node --check apps/web/risk-detail.js", workflow)
        self.assertIn("node scripts/application-intake-smoke.js", workflow)
        self.assertIn("node scripts/portfolio-dashboard-smoke.js", workflow)
        self.assertIn("node scripts/static-demo-smoke.js", workflow)
        self.assertIn("node scripts/frontend-workflow-smoke.js", workflow)

    def test_static_demo_smoke_script_exercises_reviewer_flow(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "static-demo-smoke.js").read_text(
            encoding="utf-8",
        )

        self.assertIn("MicroScoreMockApi", script)
        self.assertIn("analyst@test.com", script)
        self.assertIn("/mfi/applications", script)
        self.assertIn("/review-packet", script)
        self.assertIn("/mfi/analytics/policies", script)
        self.assertIn("MicroScorePortfolioDashboard", script)
        self.assertIn("portfolio_dashboard_v2", script)
        self.assertIn("session_expiry_visible", script)
        self.assertIn("/mfi/applications/export.csv", script)
        self.assertIn("/auth/logout", script)
        self.assertIn("logout_guard", script)
        self.assertIn("registration_guards", script)
        self.assertIn("staff_provisioning", script)
        self.assertIn("tenant_isolation", script)
        self.assertIn("resetDemo", script)
        self.assertIn("reset_applications", script)

    def test_windows_release_check_script_matches_quality_gate(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

        self.assertIn("Resolve-Python", script)
        self.assertIn("Resolve-Node", script)
        self.assertIn("unittest discover -s tests", script)
        self.assertIn("compileall", script)
        self.assertIn("src\\train_model.py", script)
        self.assertIn("microscore --regional --decision", script)
        self.assertIn("--check apps\\web\\app.js", script)
        self.assertIn("--check apps\\web\\mock-api.js", script)
        self.assertIn("--check apps\\web\\application-intake.js", script)
        self.assertIn("--check apps\\web\\portfolio-dashboard.js", script)
        self.assertIn("scripts\\static-demo-smoke.js", script)
        self.assertIn("scripts\\frontend-workflow-smoke.js", script)
        self.assertIn("scripts\\application-intake-smoke.js", script)
        self.assertIn("scripts\\portfolio-dashboard-smoke.js", script)
        self.assertIn("apps\\web\\risk-detail.js", script)
        self.assertIn("git diff --check", script)
        self.assertIn("Assert-LastExitCode", script)
        self.assertIn('throw "$Name failed with exit code $LASTEXITCODE."', script)
        self.assertIn("Ship it carefully", script)


if __name__ == "__main__":
    unittest.main()
