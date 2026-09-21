from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_admissions_case_study as admissions_report


class AdmissionsReportTests(unittest.TestCase):
    def test_source_metrics_match_report_claims(self) -> None:
        with (PROJECT_ROOT / "reports" / "research-artifacts" / "ablation_study.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            ablation_rows = list(csv.DictReader(handle))
        thin_rf = admissions_report.select_row(
            ablation_rows,
            scenario="no_late_payment_count",
            model="Random Forest",
        )
        self.assertEqual(admissions_report.metric(thin_rf["test_roc_auc"]), "0.492")

        with (
            PROJECT_ROOT
            / "reports"
            / "benchmark-artifacts"
            / "uci-default-credit-card-clients"
            / "model_metrics.csv"
        ).open("r", encoding="utf-8", newline="") as handle:
            benchmark_rows = list(csv.DictReader(handle))
        benchmark_rf = admissions_report.select_row(benchmark_rows, model="Random Forest")
        self.assertEqual(admissions_report.metric(benchmark_rf["test_roc_auc"]), "0.775")

    def test_pdf_build_contains_required_sections_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "case-study.pdf"
            admissions_report.build_pdf(output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 100_000)

            reader = PdfReader(str(output))
            self.assertEqual(len(reader.pages), 10)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            normalized_text = " ".join(text.split())
            for marker in [
                "Engineering a responsible credit-risk system",
                "A local problem, treated as a systems problem",
                "Remove one proxy and the thin-file claim collapses",
                "Monte Carlo uncertainty layer",
                "The release gate is part of the product",
                admissions_report.LIVE_REVIEW_URL,
            ]:
                self.assertIn(marker, normalized_text)


if __name__ == "__main__":
    unittest.main()
