from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.audit import (
    proxy_feature_audit,
    proxy_monitoring_table,
    segment_metrics_from_predictions,
)


class AuditTests(unittest.TestCase):
    def test_proxy_feature_audit_flags_strong_single_feature_signal(self) -> None:
        frame = pd.DataFrame(
            {
                "late_payment_count": [0, 0, 1, 2, 3, 4],
                "credit_risk": [0, 0, 0, 1, 1, 1],
            }
        )

        summary, by_value = proxy_feature_audit(frame)

        self.assertEqual(summary.loc[0, "feature"], "late_payment_count")
        self.assertGreater(summary.loc[0, "single_feature_roc_auc"], 0.9)
        self.assertEqual(summary.loc[0, "proxy_strength"], "high")
        self.assertIn("high_risk_rate", by_value.columns)

    def test_segment_metrics_from_predictions_reports_group_error_rates(self) -> None:
        segments = pd.DataFrame(
            {
                "gender": ["Female", "Female", "Male", "Male"],
            }
        )
        y_true = pd.Series([0, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 1])
        y_probability = np.array([0.2, 0.8, 0.7, 0.9])

        metrics = segment_metrics_from_predictions(
            segments,
            y_true,
            y_pred,
            y_probability,
            segment_columns=("gender",),
            model_name="Test Model",
        )

        male = metrics[metrics["segment_value"] == "Male"].iloc[0]
        self.assertEqual(male["n"], 2)
        self.assertEqual(male["false_positive_rate"], 1.0)
        self.assertEqual(male["false_negative_rate"], 0.0)

    def test_proxy_monitoring_table_tracks_adjacent_proxy_families(self) -> None:
        frame = pd.DataFrame(
            {
                "late_payment_count": [0, 0, 1, 2, 3, 4],
                "annual_income": [5000, 5200, 5100, 2500, 2200, 2000],
                "loan_application_amount": [1000, 1200, 1100, 4000, 4200, 4500],
                "total_outstanding_debt": [500, 600, 550, 3000, 3200, 3500],
                "num_open_loans": [0, 0, 1, 3, 4, 4],
                "mobile_banking_logins": [8, 9, 7, 1, 2, 1],
                "online_transfer_frequency": [4, 5, 4, 0, 1, 0],
                "atm_withdrawal_frequency": [1, 1, 2, 8, 9, 9],
                "credit_risk": [0, 0, 0, 1, 1, 1],
            }
        )

        table = proxy_monitoring_table(frame)

        self.assertIn("directional_roc_auc", table.columns)
        self.assertIn("monitoring_action", table.columns)
        self.assertIn("late_payment_count", set(table["feature"]))
        self.assertIn("monetary_scale", set(table["feature_family"]))
        self.assertIn("digital_access", set(table["feature_family"]))

        late_payment = table[table["feature"] == "late_payment_count"].iloc[0]
        self.assertEqual(late_payment["proxy_strength"], "high")
        self.assertEqual(
            late_payment["monitoring_action"],
            "must_review_before_real_data_or_kzt_claims",
        )


if __name__ == "__main__":
    unittest.main()
