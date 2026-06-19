from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"


class ResearchDocsTests(unittest.TestCase):
    def test_research_governance_docs_exist(self) -> None:
        expected_docs = [
            "ADMISSIONS_REVIEWER_BRIEF.md",
            "ARCHITECTURE.md",
            "BENCHMARK_DATASETS.md",
            "DATA_STATEMENT.md",
            "DEMO_VIDEO_SCRIPT.md",
            "DEMO_WALKTHROUGH.md",
            "ENGINEERING_QUALITY.md",
            "MODEL_CARD.md",
            "MONTE_CARLO_METHODOLOGY.md",
            "IMPACT.md",
            "PILOT_DATA_SCHEMA.md",
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
        self.assertIn("ADMISSIONS_REVIEWER_BRIEF.md", readme)
        self.assertIn("ARCHITECTURE.md", readme)
        self.assertIn("PILOT_DATA_SCHEMA.md", readme)
        self.assertIn("MONTE_CARLO_METHODOLOGY.md", readme)
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

    def test_reviewer_brief_and_architecture_define_product_story(self) -> None:
        reviewer_brief = (DOCS_ROOT / "ADMISSIONS_REVIEWER_BRIEF.md").read_text(
            encoding="utf-8",
        )
        architecture = (DOCS_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")

        self.assertIn("https://alex-tereshkovv.github.io/micro-score/", reviewer_brief)
        self.assertIn("Pavlodar", reviewer_brief)
        self.assertIn("synthetic", reviewer_brief)
        self.assertIn("not automatic lending", reviewer_brief)
        self.assertIn("thin-file", reviewer_brief)
        self.assertIn("What Not To Claim", reviewer_brief)
        self.assertIn("Human-in-the-loop", reviewer_brief)
        self.assertIn("flowchart LR", architecture)
        self.assertIn("Borrower", architecture)
        self.assertIn("MFI analyst", architecture)
        self.assertIn("Admin", architecture)
        self.assertIn("FastAPI", architecture)
        self.assertIn("GitHub Pages", architecture)
        self.assertIn("public demo mode", architecture)
        self.assertIn("Privacy Boundary", architecture)

    def test_pilot_data_schema_sets_privacy_boundaries(self) -> None:
        pilot_schema = (DOCS_ROOT / "PILOT_DATA_SCHEMA.md").read_text(
            encoding="utf-8",
        )

        self.assertIn("minimum data", pilot_schema)
        self.assertIn("GET /governance/pilot-readiness", pilot_schema)
        self.assertIn("POST /applications", pilot_schema)
        self.assertIn("sensitive behavioral-signal keys are rejected", pilot_schema)
        self.assertIn("future supervised pilot", pilot_schema)
        self.assertIn("Collect only what is needed", pilot_schema)
        self.assertIn("Keep personal identifiers separate", pilot_schema)
        self.assertIn("gender", pilot_schema)
        self.assertIn("employment_type", pilot_schema)
        self.assertIn("district", pilot_schema)
        self.assertIn("late_payment_count_12m", pilot_schema)
        self.assertIn("Do not collect", pilot_schema)
        self.assertIn("IINs", pilot_schema)
        self.assertIn("raw bank statements", pilot_schema)
        self.assertIn("segment/fairness reporting", pilot_schema)

    def test_api_contract_documents_session_security(self) -> None:
        api_contract = (DOCS_ROOT / "API_CONTRACT.md").read_text(encoding="utf-8")

        self.assertIn("POST /auth/logout", api_contract)
        self.assertIn("MICROSCORE_SESSION_TTL_HOURS", api_contract)
        self.assertIn("MICROSCORE_CORS_ORIGINS", api_contract)
        self.assertIn("expire after 8 hours", api_contract)
        self.assertIn("borrower accounts only", api_contract)
        self.assertIn("Common passwords are rejected", api_contract)
        self.assertIn("Retry-After", api_contract)
        self.assertIn("Redis or a managed", api_contract)
        self.assertIn("POST /admin/users", api_contract)
        self.assertIn("staff_user_created", api_contract)
        self.assertIn("Password hashes are never returned", api_contract)
        self.assertIn("expiring invitation links", api_contract)
        self.assertIn("GET /organizations", api_contract)
        self.assertIn("POST /admin/organizations", api_contract)
        self.assertIn("scoped", api_contract)
        self.assertIn("organization_id", api_contract)
        self.assertIn("loads this directory dynamically", api_contract)
        self.assertIn("not a replacement", api_contract)

    def test_model_registry_governance_is_documented(self) -> None:
        api_contract = (DOCS_ROOT / "API_CONTRACT.md").read_text(encoding="utf-8")
        architecture = (DOCS_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        roadmap = (DOCS_ROOT / "PRODUCT_ROADMAP.md").read_text(encoding="utf-8")

        self.assertIn("GET /mfi/model-status", api_contract)
        self.assertIn("GET /admin/model-versions", api_contract)
        self.assertIn("POST /admin/model-versions/{version}/activate", api_contract)
        self.assertIn("model_governance", api_contract)
        self.assertIn("stale_model_version", api_contract)
        self.assertIn("immutable governance snapshot", api_contract)
        self.assertIn("Model registry", architecture)
        self.assertIn("candidate/active/inactive", architecture)
        self.assertIn("stale-score detection", architecture)
        self.assertIn("model versions", roadmap)

    def test_monte_carlo_methodology_sets_statistical_boundaries(self) -> None:
        methodology = (DOCS_ROOT / "MONTE_CARLO_METHODOLOGY.md").read_text(
            encoding="utf-8"
        )
        api_contract = (DOCS_ROOT / "API_CONTRACT.md").read_text(encoding="utf-8")
        model_card = (DOCS_ROOT / "MODEL_CARD.md").read_text(encoding="utf-8")
        validation_tracker = (DOCS_ROOT / "VALIDATION_TRACKER.md").read_text(
            encoding="utf-8"
        )
        research_paper = (DOCS_ROOT / "RESEARCH_PAPER.md").read_text(encoding="utf-8")

        self.assertIn("does **not** randomize", methodology)
        self.assertIn("macro_volatility * Z_k", methodology)
        self.assertIn("common random numbers", methodology)
        self.assertIn("5th/50th/95th percentiles", methodology)
        self.assertIn("regulatory VaR", methodology)
        self.assertIn("synthetic probabilities", methodology)
        self.assertIn("default operating cost is zero", methodology)
        self.assertIn("deliberately says", methodology)
        self.assertIn("20 million", methodology)
        self.assertIn("POST /mfi/simulations/portfolio", api_contract)
        self.assertIn("portfolio_simulation_run", api_contract)
        self.assertIn("100 to 20,000", api_contract)
        self.assertIn("Monte Carlo Policy Lab", model_card)
        self.assertIn("calibration volatility", validation_tracker)
        self.assertIn("Methodological prototype only", validation_tracker)
        self.assertIn("Monte Carlo portfolio simulation", research_paper)
        self.assertIn("common random numbers", research_paper)


if __name__ == "__main__":
    unittest.main()
