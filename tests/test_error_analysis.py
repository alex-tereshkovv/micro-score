from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.error_analysis import run_error_analysis


class ErrorAnalysisTests(unittest.TestCase):
    def test_error_analysis_reports_false_positive_and_false_negative_examples(self) -> None:
        frame = pd.DataFrame(
            {
                "customer_id": [f"CUST_{index}" for index in range(20)],
                "annual_income": [
                    50_000,
                    51_000,
                    49_000,
                    50_500,
                    52_000,
                    48_500,
                    53_000,
                    47_000,
                    54_000,
                    46_000,
                    30_000,
                    29_000,
                    31_000,
                    28_500,
                    32_000,
                    27_000,
                    33_000,
                    26_500,
                    34_000,
                    26_000,
                ],
                "total_outstanding_debt": [
                    6_000,
                    5_500,
                    6_200,
                    5_800,
                    6_100,
                    5_900,
                    6_300,
                    5_700,
                    6_400,
                    5_600,
                    18_000,
                    19_000,
                    17_500,
                    20_000,
                    17_000,
                    20_500,
                    16_500,
                    21_000,
                    16_000,
                    21_500,
                ],
                "mobile_banking_logins": [20, 21, 19, 18, 22, 17, 23, 16, 24, 15, 3, 4, 3, 5, 4, 2, 5, 2, 6, 1],
                "online_transfer_frequency": [9, 8, 10, 7, 11, 6, 12, 5, 13, 4, 1, 1, 2, 1, 2, 0, 2, 0, 3, 0],
                "atm_withdrawal_frequency": [2, 3, 2, 3, 1, 4, 1, 4, 1, 5, 9, 8, 10, 8, 9, 11, 8, 12, 7, 13],
                "avg_deposit_amount": [1_400, 1_350, 1_450, 1_300, 1_500, 1_250, 1_550, 1_200, 1_600, 1_150, 300, 280, 320, 260, 340, 240, 360, 220, 380, 200],
                "debit_card_spending": [900, 880, 920, 860, 940, 840, 960, 820, 980, 800, 1_700, 1_750, 1_650, 1_800, 1_600, 1_850, 1_550, 1_900, 1_500, 1_950],
                "loan_application_amount": [3_000, 3_100, 2_900, 3_200, 2_800, 3_300, 2_700, 3_400, 2_600, 3_500, 8_000, 8_200, 7_800, 8_400, 7_600, 8_600, 7_400, 8_800, 7_200, 9_000],
                "num_open_loans": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 4, 4, 3, 5, 3, 5, 3, 5, 2, 6],
                "late_payment_count": [0, 0, 1, 0, 1, 0, 1, 0, 2, 0, 4, 5, 4, 5, 3, 5, 3, 5, 2, 5],
                "credit_score": [700, 710, 690, 705, 695, 700, 690, 705, 680, 710, 500, 490, 510, 480, 520, 470, 530, 460, 540, 450],
                "loan_default_history": [0] * 10 + [1] * 10,
                "fraud_flag": [0] * 20,
                "gender": ["Female", "Male"] * 10,
                "employment_status": ["Employed"] * 10 + ["Self-employed"] * 10,
                "credit_risk": [0] * 10 + [1] * 10,
            }
        )

        report = run_error_analysis(
            frame=frame,
            random_state=5,
            test_size=0.4,
            threshold=0.5,
            example_limit=5,
            min_group_size=1,
        )

        self.assertIn("false_positive_rate", report.summary.columns)
        self.assertIn("false_negative_rate", report.summary.columns)
        self.assertIn("decision_meaning", report.false_positive_examples.columns)
        self.assertIn("decision_meaning", report.false_negative_examples.columns)
        self.assertIn("segment_feature", report.segment_errors.columns)
        self.assertEqual(len(report.all_predictions), 8)


if __name__ == "__main__":
    unittest.main()
