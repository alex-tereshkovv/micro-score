from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.features import DEFAULT_DROP_COLUMNS, make_model_frame


class FeatureEngineeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "customer_id": ["CUST_1", "CUST_2"],
                "annual_income": [1000.0, 2000.0],
                "total_outstanding_debt": [250.0, 500.0],
                "mobile_banking_logins": [3, 5],
                "online_transfer_frequency": [2, 1],
                "atm_withdrawal_frequency": [1, 2],
                "avg_deposit_amount": [100.0, 300.0],
                "debit_card_spending": [50.0, 150.0],
                "loan_application_amount": [200.0, 400.0],
                "num_open_loans": [1, 0],
                "credit_score": [650, 500],
                "loan_default_history": [0, 1],
                "fraud_flag": [0, 0],
                "gender": ["Female", "Male"],
                "credit_risk": [0, 1],
            }
        )

    def test_model_frame_drops_identifier_and_leakage_columns(self) -> None:
        features, target = make_model_frame(self.frame)

        self.assertEqual(target.tolist(), [0, 1])
        self.assertNotIn("credit_risk", features.columns)
        for column in DEFAULT_DROP_COLUMNS:
            self.assertNotIn(column, features.columns)

    def test_model_frame_adds_behavioral_features(self) -> None:
        features, _target = make_model_frame(self.frame)

        expected_features = {
            "income_to_debt_ratio",
            "digital_activity_score",
            "deposit_to_spending_ratio",
            "loan_to_income_ratio",
            "total_credit_pressure",
            "debt_per_open_loan",
        }
        self.assertTrue(expected_features.issubset(set(features.columns)))

    def test_missing_target_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Target column"):
            make_model_frame(self.frame.drop(columns=["credit_risk"]))


if __name__ == "__main__":
    unittest.main()
