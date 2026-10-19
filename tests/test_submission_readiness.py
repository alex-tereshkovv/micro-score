from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "reports" / "submission" / "manifest.json"
MODULE_PATH = PROJECT_ROOT / "scripts" / "build-submission-manifest.py"
SPEC = importlib.util.spec_from_file_location("build_submission_manifest", MODULE_PATH)
assert SPEC and SPEC.loader
submission_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(submission_manifest)
DEFENSE_PATH = PROJECT_ROOT / "reports" / "submission" / "technical-defense.json"
DEFENSE_MODULE_PATH = PROJECT_ROOT / "scripts" / "build-technical-defense-packet.py"
DEFENSE_SPEC = importlib.util.spec_from_file_location(
    "build_technical_defense_packet", DEFENSE_MODULE_PATH
)
assert DEFENSE_SPEC and DEFENSE_SPEC.loader
technical_defense = importlib.util.module_from_spec(DEFENSE_SPEC)
DEFENSE_SPEC.loader.exec_module(technical_defense)


def pdf_text(path: Path) -> tuple[int, str]:
    reader = PdfReader(str(path))
    return len(reader.pages), " ".join(
        " ".join(page.extract_text() or "" for page in reader.pages).split()
    )


class SubmissionReadinessTests(unittest.TestCase):
    def test_committed_manifest_is_deterministic_and_current(self) -> None:
        expected = submission_manifest.serialized_manifest()
        actual = MANIFEST_PATH.read_text(encoding="utf-8")
        self.assertEqual(actual, expected)
        self.assertEqual(
            DEFENSE_PATH.read_text(encoding="utf-8"),
            technical_defense.serialized_packet(),
        )

    def test_manifest_has_unique_hashed_artifacts_and_blocked_production_claim(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        paths = [item["path"] for item in payload["artifacts"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertGreaterEqual(len(paths), 20)
        self.assertEqual(payload["status"], "review_ready_not_production_ready")
        self.assertEqual(payload["quality_gate"]["python_tests"], 152)
        self.assertEqual(payload["quality_gate"]["local_smoke_workflows"], 13)
        self.assertIn("reports/submission/technical-defense.json", paths)
        for item in payload["artifacts"]:
            self.assertIn(item["hash_mode"], {"utf8_lf", "binary"})
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(item["bytes"], 0)

        defense = json.loads(DEFENSE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(defense["schema_version"], "microscore-technical-defense-v1")
        self.assertEqual(defense["status"], "owner_rehearsal_required")
        self.assertEqual(len(defense["questions"]), 12)
        self.assertIn("oral understanding", defense["automated_gate_scope"])
        manifest_claims = {
            item["key"]: (item["value"], item["evidence_class"])
            for item in payload["headline_claims"]
        }
        defense_claims = {
            item["key"]: (item["value"], item["evidence_class"])
            for item in defense["headline_claims"]
        }
        self.assertEqual(defense_claims, manifest_claims)

    def test_public_counts_and_research_findings_are_synchronized(self) -> None:
        sources = [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "apps" / "web" / "index.html",
            PROJECT_ROOT / "apps" / "web" / "showcase.html",
            PROJECT_ROOT / "apps" / "web" / "evidence.html",
            PROJECT_ROOT / "docs" / "DEMO_VIDEO_SCRIPT.md",
        ]
        for source in sources:
            self.assertIn("152", source.read_text(encoding="utf-8"), source.name)
        evidence = sources[3].read_text(encoding="utf-8")
        self.assertIn("13 local smoke workflows", evidence)
        paper = (PROJECT_ROOT / "docs" / "RESEARCH_PAPER.md").read_text(
            encoding="utf-8"
        )
        findings = [
            int(value)
            for value in re.findall(
                r"^### Research Finding (\d+):", paper, flags=re.MULTILINE
            )
        ]
        self.assertEqual(findings, list(range(1, 9)))

    def test_pdfs_contain_current_quality_evidence_and_limits(self) -> None:
        case_pages, case_text = pdf_text(
            PROJECT_ROOT / "output" / "pdf" / "MicroScore_Engineering_Case_Study.pdf"
        )
        paper_pages, paper_text = pdf_text(
            PROJECT_ROOT / "output" / "pdf" / "MicroScore_Research_Paper.pdf"
        )
        self.assertGreaterEqual(case_pages, 10)
        self.assertLessEqual(case_pages, 11)
        self.assertEqual(paper_pages, 11)
        self.assertIn("152", case_text)
        self.assertIn("0.830", case_text)
        self.assertIn("0.492", case_text)
        self.assertIn("production readiness stays blocked", case_text.lower())
        self.assertIn("Research Finding 8", paper_text)
        self.assertIn("not validated for real lending", paper_text.lower())

    def test_reviewer_surfaces_do_not_revive_stale_submission_language(self) -> None:
        paths = [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs" / "PROJECT_BRIEF.md",
            PROJECT_ROOT / "docs" / "RELEASE_CANDIDATE.md",
            PROJECT_ROOT / "apps" / "web" / "evidence.html",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("Admissions Reviewer Brief", combined)
        self.assertNotIn("ADMISSIONS_REVIEWER_BRIEF.md", combined)
        self.assertNotRegex(combined, r"\b(?:126|142|147)\s+(?:automated|Python) tests\b")


if __name__ == "__main__":
    unittest.main()
