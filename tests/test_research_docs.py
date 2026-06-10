from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"


class ResearchDocsTests(unittest.TestCase):
    def test_research_governance_docs_exist(self) -> None:
        expected_docs = [
            "DATA_STATEMENT.md",
            "MODEL_CARD.md",
            "IMPACT.md",
            "RESEARCH_PAPER.md",
        ]

        for filename in expected_docs:
            self.assertTrue((DOCS_ROOT / filename).exists(), filename)

    def test_readme_has_portfolio_snapshot(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("## Snapshot", readme)
        self.assertIn("Interpretable alternative credit-risk scoring prototype", readme)
        self.assertIn("Public demo", readme)
        self.assertIn("Research Findings", readme)
        self.assertIn("Key limitation", readme)

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


if __name__ == "__main__":
    unittest.main()
