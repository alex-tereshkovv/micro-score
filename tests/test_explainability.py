from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore import logistic_local_explanation as public_logistic_local_explanation
from microscore.explainability import logistic_local_explanation
from microscore.features import make_model_frame
from microscore.modeling import build_logistic_regression


class ExplainabilityTests(unittest.TestCase):
    def test_logistic_explanation_matches_model_probability(self) -> None:
        frame = pd.DataFrame(
            {
                "customer_id": [f"CUST_{index}" for index in range(8)],
                "annual_income": [50_000, 48_000, 52_000, 49_000, 30_000, 31_000, 29_000, 28_000],
                "total_outstanding_debt": [5_000, 6_000, 5_500, 5_200, 18_000, 17_000, 19_000, 20_000],
                "mobile_banking_logins": [25, 22, 24, 21, 4, 5, 3, 4],
                "online_transfer_frequency": [11, 9, 10, 8, 1, 2, 1, 1],
                "atm_withdrawal_frequency": [2, 2, 3, 3, 9, 8, 10, 11],
                "avg_deposit_amount": [1_500, 1_450, 1_600, 1_520, 300, 350, 280, 250],
                "debit_card_spending": [900, 850, 920, 880, 1_700, 1_600, 1_800, 1_900],
                "loan_application_amount": [3_000, 2_800, 3_100, 3_200, 8_000, 7_500, 8_500, 9_000],
                "num_open_loans": [1, 1, 1, 1, 4, 3, 4, 5],
                "late_payment_count": [0, 0, 0, 1, 3, 4, 5, 5],
                "credit_score": [700, 705, 710, 690, 520, 510, 500, 495],
                "loan_default_history": [0, 0, 0, 0, 1, 1, 1, 1],
                "fraud_flag": [0, 0, 0, 0, 0, 0, 0, 0],
                "gender": ["Female", "Male", "Female", "Male", "Female", "Male", "Female", "Male"],
                "employment_status": ["Employed", "Employed", "Self-employed", "Employed", "Unemployed", "Unemployed", "Self-employed", "Unemployed"],
                "credit_risk": [0, 0, 0, 0, 1, 1, 1, 1],
            }
        )
        X, y = make_model_frame(frame)
        estimator = build_logistic_regression(random_state=7)
        estimator.fit(X, y)

        explanation = logistic_local_explanation(estimator, X.iloc[[0]])
        model_probability = float(estimator.predict_proba(X.iloc[[0]])[0, 1])

        self.assertAlmostEqual(explanation.high_risk_probability, model_probability, places=10)
        self.assertAlmostEqual(
            explanation.predicted_log_odds,
            explanation.baseline_log_odds + explanation.total_contribution,
            places=10,
        )
        self.assertGreater(len(explanation.top_factors), 0)
        self.assertTrue(
            all(factor.direction == "increases_risk" for factor in explanation.top_positive_factors)
        )
        self.assertTrue(
            all(factor.direction == "reduces_risk" for factor in explanation.top_protective_factors)
        )
        self.assertIs(public_logistic_local_explanation, logistic_local_explanation)


if __name__ == "__main__":
    unittest.main()
