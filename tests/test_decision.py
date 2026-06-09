from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.decision import segment_approval_table, threshold_decision_table


class DecisionAnalysisTests(unittest.TestCase):
    def test_threshold_table_reports_profit_and_approval_tradeoffs(self) -> None:
        y_true = pd.Series([0, 0, 1, 1])
        y_probability = np.array([0.1, 0.3, 0.7, 0.9])
        loan_amount = pd.Series([1000.0, 1000.0, 1000.0, 1000.0])

        table = threshold_decision_table(
            y_true,
            y_probability,
            loan_amount,
            thresholds=np.array([0.2, 0.8]),
            interest_margin=0.2,
            loss_given_default=0.6,
        )

        low_threshold = table[table["threshold"] == 0.2].iloc[0]
        high_threshold = table[table["threshold"] == 0.8].iloc[0]

        self.assertEqual(low_threshold["approved_count"], 1)
        self.assertEqual(low_threshold["default_rate_among_approved"], 0.0)
        self.assertEqual(high_threshold["approved_count"], 3)
        self.assertAlmostEqual(high_threshold["expected_profit_total"], -200.0)

    def test_segment_approval_table_slices_by_group(self) -> None:
        segments = pd.DataFrame(
            {
                "settlement_type": ["urban", "urban", "rural", "rural"],
            }
        )
        y_true = pd.Series([0, 1, 0, 1])
        y_probability = np.array([0.2, 0.8, 0.3, 0.4])

        table = segment_approval_table(
            segments,
            y_true,
            y_probability,
            threshold=0.5,
            segment_columns=("settlement_type",),
        )

        rural = table[table["segment_value"] == "rural"].iloc[0]
        self.assertEqual(rural["n"], 2)
        self.assertEqual(rural["approval_rate"], 1.0)
        self.assertEqual(rural["default_rate_among_approved"], 0.5)


if __name__ == "__main__":
    unittest.main()
