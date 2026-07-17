from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore import generate_research_artifacts
from microscore.modeling import build_logistic_regression


def _sample_credit_frame(rows: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(23)
    credit_risk = np.array([0, 1] * (rows // 2))
    return pd.DataFrame(
        {
            "customer_id": [f"CUST_{index:04d}" for index in range(rows)],
            "age": rng.integers(21, 61, size=rows),
            "gender": np.where(np.arange(rows) % 2 == 0, "Female", "Male"),
            "employment_status": np.where(np.arange(rows) % 3 == 0, "Employed", "Self-employed"),
            "annual_income": rng.normal(3_200_000, 450_000, size=rows).clip(500_000),
            "account_age_months": rng.integers(3, 80, size=rows),
            "avg_monthly_balance": rng.normal(180_000, 50_000, size=rows).clip(10_000),
            "num_deposits_per_month": rng.integers(1, 8, size=rows),
            "avg_deposit_amount": rng.normal(75_000, 20_000, size=rows).clip(5_000),
            "debit_card_usage_frequency": rng.integers(2, 40, size=rows),
            "debit_card_spending": rng.normal(120_000, 30_000, size=rows).clip(5_000),
            "mobile_banking_logins": rng.integers(1, 60, size=rows),
            "online_transfer_frequency": rng.integers(0, 25, size=rows),
            "atm_withdrawal_frequency": rng.integers(0, 15, size=rows),
            "credit_score": 720 - credit_risk * 120 + rng.integers(-20, 20, size=rows),
            "num_open_loans": rng.integers(0, 5, size=rows),
            "total_outstanding_debt": rng.normal(420_000, 130_000, size=rows).clip(0),
            "late_payment_count": credit_risk * 3 + rng.integers(0, 2, size=rows),
            "loan_default_history": credit_risk,
            "fraud_flag": np.zeros(rows, dtype=int),
            "loan_application_amount": rng.normal(300_000, 80_000, size=rows).clip(20_000),
            "credit_risk": credit_risk,
        }
    )


class ReportingTests(unittest.TestCase):
    def test_generate_research_artifacts_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            factories = {
                "Logistic Regression": lambda: build_logistic_regression(23),
            }
            artifacts = generate_research_artifacts(
                frame=_sample_credit_frame(),
                output_dir=tempdir,
                model_factories=factories,
                ablation_model_factories=factories,
                random_state=23,
                n_bins=5,
            )

            for path in artifacts.files:
                self.assertTrue(path.exists(), path)

            manifest = json.loads(artifacts.manifest_json.read_text(encoding="utf-8"))
            self.assertEqual(manifest["project"], "MicroScore")
            self.assertEqual(manifest["rows"], 80)

            model_metrics = pd.read_csv(artifacts.model_metrics_csv)
            ablation = pd.read_csv(artifacts.ablation_csv)
            proxy_monitoring = pd.read_csv(artifacts.proxy_monitoring_csv)
            calibration = pd.read_csv(artifacts.calibration_csv)
            error_summary = pd.read_csv(artifacts.error_summary_csv)
            segment_errors = pd.read_csv(artifacts.segment_error_csv)
            false_positives = pd.read_csv(artifacts.false_positive_examples_csv)
            false_negatives = pd.read_csv(artifacts.false_negative_examples_csv)
            policy_analysis = pd.read_csv(artifacts.policy_analysis_csv)
            segment_policy = pd.read_csv(artifacts.segment_policy_analysis_csv)
            explanation_summary = pd.read_csv(artifacts.explanation_summary_csv)
            explanation_factors = pd.read_csv(artifacts.explanation_factors_csv)

            self.assertIn("test_brier_score", model_metrics.columns)
            self.assertIn("delta_test_roc_auc_vs_no_leakage", ablation.columns)
            self.assertIn("directional_roc_auc", proxy_monitoring.columns)
            self.assertIn("monitoring_action", proxy_monitoring.columns)
            self.assertIn("calibration_error", calibration.columns)
            self.assertIn("false_positive_rate", error_summary.columns)
            self.assertIn("false_negative_rate", segment_errors.columns)
            self.assertIn("decision_meaning", false_positives.columns)
            self.assertIn("decision_meaning", false_negatives.columns)
            self.assertIn("auto_approval_rate", policy_analysis.columns)
            self.assertIn("manual_review_rate", segment_policy.columns)
            self.assertIn("high_risk_probability", explanation_summary.columns)
            self.assertIn("direction", explanation_factors.columns)
            self.assertIn(
                "MicroScore Research Artifacts",
                artifacts.summary_markdown.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Proxy Monitoring v2",
                artifacts.summary_markdown.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                manifest["monetary_warning"],
                "Prototype amount units; not calibrated KZT.",
            )
            self.assertIn("proxy_monitoring.csv", manifest["files"])


if __name__ == "__main__":
    unittest.main()
