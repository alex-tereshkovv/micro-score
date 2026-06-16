from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"


class ResearchDocsTests(unittest.TestCase):
    def test_research_governance_docs_exist(self) -> None:
        expected_docs = [
            "BENCHMARK_DATASETS.md",
            "DATA_STATEMENT.md",
            "DEMO_VIDEO_SCRIPT.md",
            "DEMO_WALKTHROUGH.md",
            "ENGINEERING_QUALITY.md",
            "MODEL_CARD.md",
            "IMPACT.md",
            "PUBLIC_DEMO_PLAN.md",
            "RELEASE_CHECKLIST.md",
            "RESEARCH_PAPER.md",
            "SCREENSHOT_CHECKLIST.md",
            "STAKEHOLDER_INTERVIEW_GUIDE.md",
            "STATIC_DEMO_DEPLOYMENT.md",
            "VALIDATION_TRACKER.md",
        ]

        for filename in expected_docs:
            self.assertTrue((DOCS_ROOT / filename).exists(), filename)

    def test_readme_has_portfolio_snapshot(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("## Snapshot", readme)
        self.assertIn("## Try The Live Demo", readme)
        self.assertIn("## Developer Quick Start (Optional)", readme)
        self.assertIn("Interpretable alternative credit-risk scoring prototype", readme)
        self.assertIn("Public demo", readme)
        self.assertIn("https://alex-tereshkovv.github.io/micro-score/", readme)
        self.assertIn("borrower@test.com", readme)
        self.assertIn("password123", readme)
        self.assertIn("DEMO_VIDEO_SCRIPT.md", readme)
        self.assertIn("SCREENSHOT_CHECKLIST.md", readme)
        self.assertIn("Why This Matters", readme)
        self.assertIn("Research Findings", readme)
        self.assertIn("Key limitation", readme)
        self.assertLess(len(readme.splitlines()), 240)
        self.assertNotIn(r".venv\S cripts\p ython", readme)
        self.assertNotIn(r".venv\Scripts\p ython", readme)
        self.assertNotIn(r".venv\S cripts\python", readme)

    def test_data_statement_separates_evidence_and_assumptions(self) -> None:
        data_statement = (DOCS_ROOT / "DATA_STATEMENT.md").read_text(encoding="utf-8")
        external_readme = (PROJECT_ROOT / "data" / "external" / "README.md").read_text(
            encoding="utf-8"
        )

        for text in [data_statement, external_readme]:
            self.assertIn("Evidence-based", text)
            self.assertIn("Assumption", text)
            self.assertIn("Needs validation", text)

    def test_model_card_defines_non_use_and_oversight(self) -> None:
        model_card = (DOCS_ROOT / "MODEL_CARD.md").read_text(encoding="utf-8")

        self.assertIn("Not Intended Use", model_card)
        self.assertIn("Human Oversight", model_card)
        self.assertIn("Privacy Risks", model_card)

    def test_validation_docs_define_safe_feedback_collection(self) -> None:
        interview_guide = (DOCS_ROOT / "STAKEHOLDER_INTERVIEW_GUIDE.md").read_text(
            encoding="utf-8"
        )
        validation_tracker = (DOCS_ROOT / "VALIDATION_TRACKER.md").read_text(
            encoding="utf-8"
        )
        feedback_template = (
            PROJECT_ROOT / "data" / "validation" / "stakeholder_feedback_template.csv"
        ).read_text(encoding="utf-8")

        self.assertIn("Do Not Collect", interview_guide)
        self.assertIn("Consent Script", interview_guide)
        self.assertIn("Validation Milestones", validation_tracker)
        self.assertIn("contains_personal_data", feedback_template)

    def test_demo_and_benchmark_docs_define_portfolio_next_steps(self) -> None:
        demo_plan = (DOCS_ROOT / "PUBLIC_DEMO_PLAN.md").read_text(encoding="utf-8")
        benchmark_plan = (DOCS_ROOT / "BENCHMARK_DATASETS.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Live Demo", demo_plan)
        self.assertIn("Two-Minute Video Outline", demo_plan)
        self.assertIn("DEMO_WALKTHROUGH.md", demo_plan)
        self.assertIn("DEMO_VIDEO_SCRIPT.md", demo_plan)
        self.assertIn("SCREENSHOT_CHECKLIST.md", demo_plan)
        self.assertIn("RELEASE_CHECKLIST.md", demo_plan)
        self.assertIn("UCI Default of Credit Card Clients", benchmark_plan)
        self.assertIn("Home Credit Default Risk", benchmark_plan)
        self.assertIn("synthetic Pavlodar", benchmark_plan)

    def test_reviewer_demo_assets_define_safe_walkthrough(self) -> None:
        walkthrough = (DOCS_ROOT / "DEMO_WALKTHROUGH.md").read_text(encoding="utf-8")
        release_checklist = (DOCS_ROOT / "RELEASE_CHECKLIST.md").read_text(
            encoding="utf-8",
        )
        static_deployment = (DOCS_ROOT / "STATIC_DEMO_DEPLOYMENT.md").read_text(
            encoding="utf-8",
        )
        video_script = (DOCS_ROOT / "DEMO_VIDEO_SCRIPT.md").read_text(encoding="utf-8")
        screenshot_checklist = (DOCS_ROOT / "SCREENSHOT_CHECKLIST.md").read_text(
            encoding="utf-8",
        )

        self.assertIn("http://127.0.0.1:5173?demo=static", walkthrough)
        self.assertIn("borrower@test.com", walkthrough)
        self.assertIn("analyst@test.com", walkthrough)
        self.assertIn("admin@test.com", walkthrough)
        self.assertIn("What Not To Claim", walkthrough)
        self.assertIn("reviewer snapshot", walkthrough)
        self.assertIn("model-use notice", walkthrough)
        self.assertIn("synthetic data only", walkthrough)
        self.assertIn("not a legal credit decision", walkthrough)
        self.assertIn("confirms that only synthetic", walkthrough)
        self.assertIn("Release Checklist", release_checklist)
        self.assertIn("scripts\\check.ps1", release_checklist)
        self.assertIn("Login screen reviewer snapshot", release_checklist)
        self.assertIn("Demo Video Script", release_checklist)
        self.assertIn("Screenshot Checklist", release_checklist)
        self.assertIn("consent checkbox", release_checklist)
        self.assertIn("model-use notice", release_checklist)
        self.assertIn("Static demo smoke test", release_checklist)
        self.assertIn("No real borrower", release_checklist)
        self.assertIn("Reset demo", release_checklist)
        self.assertIn("hides local API settings", release_checklist)
        self.assertIn("loading", release_checklist)
        self.assertIn("error states", release_checklist)
        self.assertIn("hides local API settings", static_deployment)
        self.assertIn("localhost ports", static_deployment)
        self.assertIn("0:00 - 0:15 Opening", video_script)
        self.assertIn("What Not To Say", video_script)
        self.assertIn("borrower@test.com", video_script)
        self.assertIn("not ready for real loan approval", video_script)
        self.assertIn("docs/assets/screenshots/", screenshot_checklist)
        self.assertIn("01-login-reviewer-snapshot.png", screenshot_checklist)
        self.assertIn("Score Detail + Model-Use Notice", screenshot_checklist)
        self.assertIn("No real borrower data", screenshot_checklist)
        self.assertTrue((DOCS_ROOT / "assets" / "screenshots" / ".gitkeep").exists())


if __name__ == "__main__":
    unittest.main()
