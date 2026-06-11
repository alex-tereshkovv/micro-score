from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

WEB_ROOT = PROJECT_ROOT / "apps" / "web"


class WebStaticTests(unittest.TestCase):
    def test_frontend_files_are_present(self) -> None:
        self.assertTrue((WEB_ROOT / "index.html").exists())
        self.assertTrue((WEB_ROOT / "styles.css").exists())
        self.assertTrue((WEB_ROOT / "app.js").exists())
        self.assertTrue((WEB_ROOT / "README.md").exists())
        self.assertTrue((WEB_ROOT / "assets" / "favicon.svg").exists())
        self.assertTrue((WEB_ROOT / "assets" / "favicon-32.png").exists())
        self.assertTrue((WEB_ROOT / "assets" / "apple-touch-icon.png").exists())
        self.assertTrue((WEB_ROOT / "assets" / "microscore-mark.svg").exists())
        self.assertTrue((WEB_ROOT / "assets" / "micro-score.png").exists())

    def test_html_loads_styles_and_script(self) -> None:
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="./styles.css"', html)
        self.assertIn('href="./assets/favicon.svg"', html)
        self.assertIn('href="./assets/favicon-32.png"', html)
        self.assertIn('href="./assets/apple-touch-icon.png"', html)
        self.assertIn('href="./assets/micro-score.png"', html)
        self.assertIn('src="./assets/microscore-mark.svg"', html)
        self.assertIn('src="./app.js"', html)
        self.assertIn('id="borrowerView"', html)
        self.assertIn('id="mfiView"', html)
        self.assertIn('id="adminView"', html)

    def test_frontend_targets_current_api_contract(self) -> None:
        markup = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        expected_paths = [
            "/health",
            "/auth/register",
            "/auth/login",
            "/applications",
            "/mfi/applications",
            "/decision",
            "/mfi/analytics/segments",
            "/mfi/analytics/policies",
            "/mfi/analytics/decisions",
            "/admin/audit-events",
            "/admin/applications",
        ]
        for path in expected_paths:
            self.assertIn(path, script)
        self.assertIn("Scenario comparison", script)
        self.assertIn("Recommendation", script)
        self.assertIn("Local explanation", script)
        self.assertIn("MFI decision", script)
        self.assertIn("saveApplicationDecision", script)
        self.assertIn("Analyst decisions", script)
        self.assertIn("renderPortfolioDecisionSnapshot", script)
        self.assertIn("Decision audit", markup)
        self.assertIn("decisionAuditRows", script)
        self.assertIn("proxy_sensitivity_delta", script)
        self.assertIn("decision_support", script)
        self.assertIn("top_positive_factors", script)
        self.assertIn("top_protective_factors", script)
        self.assertIn("Portfolio", markup)
        self.assertIn("renderDistrictRiskRows", script)
        self.assertIn("renderPortfolioOverview", script)
        self.assertIn("Policy Lab", markup)
        self.assertIn("renderPolicyAnalytics", script)
        self.assertIn("resetApplicationViews", script)
        self.assertIn('removeItem("microscore.lastApplicationId")', script)


if __name__ == "__main__":
    unittest.main()
