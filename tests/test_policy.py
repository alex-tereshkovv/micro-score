from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.policy import ThresholdPolicy, policy_decision_table, segment_policy_table


class PolicyAnalysisTests(unittest.TestCase):
    def test_policy_decision_table_reports_approve_review_decline_tradeoffs(self) -> None:
        table = policy_decision_table(
            pd.Series([0, 0, 1, 1]),
            np.array([0.10, 0.40, 0.60, 0.90]),
            pd.Series([1000, 1000, 1000, 1000]),
            policies=(
                ThresholdPolicy(
                    name="test_policy",
                    approve_threshold=0.30,
                    decline_threshold=0.80,
                    description="Test policy",
                ),
            ),
        )

        row = table.iloc[0]

        self.assertEqual(row["auto_approve_count"], 1)
        self.assertEqual(row["manual_review_count"], 2)
        self.assertEqual(row["auto_decline_count"], 1)
        self.assertEqual(row["high_risk_approval_rate"], 0.0)
        self.assertEqual(row["good_borrower_auto_decline_rate"], 0.0)
        self.assertAlmostEqual(row["expected_profit_auto_approved_total"], 220.0)

    def test_segment_policy_table_reports_group_action_rates(self) -> None:
        segments = pd.DataFrame(
            {
                "gender": ["Female", "Female", "Male", "Male"],
            }
        )
        table = segment_policy_table(
            segments,
            pd.Series([0, 1, 0, 1]),
            np.array([0.10, 0.40, 0.60, 0.90]),
            policies=(
                ThresholdPolicy(
                    name="test_policy",
                    approve_threshold=0.30,
                    decline_threshold=0.80,
                    description="Test policy",
                ),
            ),
            segment_columns=("gender",),
            min_group_size=1,
        )

        female = table[table["segment_value"] == "Female"].iloc[0]
        male = table[table["segment_value"] == "Male"].iloc[0]

        self.assertEqual(female["auto_approval_rate"], 0.5)
        self.assertEqual(female["manual_review_rate"], 0.5)
        self.assertEqual(male["manual_review_rate"], 0.5)
        self.assertEqual(male["auto_decline_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
