from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.audit import proxy_feature_audit, segment_metrics_from_predictions


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


if __name__ == "__main__":
    unittest.main()
