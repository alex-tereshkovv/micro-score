from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.modeling import calibration_table, results_table
from microscore import calibration_table as public_calibration_table


class ModelingTests(unittest.TestCase):
    def test_calibration_table_reports_probability_bins(self) -> None:
        table = calibration_table(
            pd.Series([0, 0, 1, 1]),
            np.array([0.1, 0.2, 0.8, 0.9]),
            n_bins=2,
        )

        self.assertEqual(table["n"].sum(), 4)
        self.assertIn("actual_high_risk_rate", table.columns)
        self.assertIn("calibration_error", table.columns)
        self.assertIs(public_calibration_table, calibration_table)

    def test_results_table_includes_brier_score(self) -> None:
        class Result:
            name = "Test Model"
            test_metrics = {
                "accuracy": 1.0,
                "roc_auc": 1.0,
                "brier_score": 0.1,
            }
            cv_metrics = {}

        table = results_table([Result()])

        self.assertIn("test_brier_score", table.columns)


if __name__ == "__main__":
    unittest.main()
