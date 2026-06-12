from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

WEB_ROOT = PROJECT_ROOT / "apps" / "web"


class WebStaticTests(unittest.TestCase):
    def test_frontend_files_are_present(self) -> None:
        self.assertTrue((PROJECT_ROOT / "Start-MicroScore.cmd").exists())
        self.assertTrue((WEB_ROOT / "index.html").exists())
        self.assertTrue((WEB_ROOT / "styles.css").exists())
        self.assertTrue((WEB_ROOT / "app.js").exists())
        self.assertTrue((WEB_ROOT / "README.md").exists())
        self.assertTrue((WEB_ROOT / "assets" / "favicon.svg").exists())
        self.assertTrue((WEB_ROOT / "assets" / "favicon-32.png").exists())
        self.assertTrue((WEB_ROOT / "assets" / "apple-touch-icon.png").exists())
        self.assertTrue((WEB_ROOT / "assets" / "microscore-mark.svg").exists())
        self.assertTrue((WEB_ROOT / "assets" / "micro-score.png").exists())
        self.assertTrue((WEB_ROOT / "assets" / "micro-score-lockup.png").exists())

    def test_html_loads_styles_and_script(self) -> None:
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="./styles.css"', html)
        self.assertIn('href="./assets/favicon.svg"', html)
        self.assertIn('href="./assets/favicon-32.png"', html)
        self.assertIn('href="./assets/apple-touch-icon.png"', html)
        self.assertIn('href="./assets/micro-score.png"', html)
        self.assertIn('src="./assets/micro-score-lockup.png?v=20260612-full"', html)
        self.assertIn('src="./assets/microscore-mark.svg"', html)
        self.assertIn('src="./app.js?v=20260612-routes"', html)
        self.assertIn("window.history.replaceState", html)
        self.assertIn('id="authScreen"', html)
        self.assertIn('id="appShell"', html)
        self.assertIn('hidden', html)
        self.assertIn('id="borrowerView"', html)
        self.assertIn('id="mfiView"', html)
        self.assertIn('id="adminView"', html)

    def test_hidden_screens_are_not_scrollable_before_login(self) -> None:
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("[hidden]", styles)
        self.assertIn("display: none !important;", styles)

    def test_frontend_targets_current_api_contract(self) -> None:
        markup = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        expected_paths = [
            "/health",
            "/auth/register",
            "/auth/login",
            "/applications",
            "/timeline",
            "/mfi/applications",
            "/mfi/applications/export.csv",
            "/decision",
            "/review-packet",
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
        self.assertIn("Review packet", markup)
        self.assertIn("loadReviewPacket", script)
        self.assertIn("renderReviewPacket", script)
        self.assertIn("Application timeline", script)
        self.assertIn("renderApplicationTimeline", script)
        self.assertIn("Export CSV", markup)
        self.assertIn("exportApplicationsCsv", script)
        self.assertIn("microscore-applications.csv", script)
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
        self.assertIn("API_BASE_CANDIDATES", script)
        self.assertIn("enterDemoWorkspace", script)
        self.assertIn("API settings", markup)
        self.assertIn("roleAllowedViews", script)
        self.assertIn("configureRoleNavigation", script)
        self.assertIn("setAppMode", script)
        self.assertIn("routeToView", script)
        self.assertIn("viewToRoute", script)
        self.assertIn("roleDefaultRoutes", script)
        self.assertIn("applyRoute", script)
        self.assertIn("replaceRoute", script)
        self.assertIn("hashchange", script)
        self.assertIn("#/login", script)
        self.assertIn("#/borrower", script)
        self.assertIn("#/mfi", script)
        self.assertIn("#/admin", script)
        self.assertIn('data-roles="borrower"', markup)
        self.assertIn('data-roles="mfi_analyst admin"', markup)
        self.assertIn('data-roles="admin"', markup)

    def test_one_click_launcher_is_documented(self) -> None:
        root_readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        web_readme = (WEB_ROOT / "README.md").read_text(encoding="utf-8")
        command_file = (PROJECT_ROOT / "Start-MicroScore.cmd").read_text(encoding="utf-8")

        self.assertIn("Start-MicroScore.cmd", root_readme)
        self.assertIn("Start-MicroScore.cmd", web_readme)
        self.assertIn("microscore_api.dev", command_file)


if __name__ == "__main__":
    unittest.main()
