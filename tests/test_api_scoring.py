from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.scoring import get_scoring_service, risk_band


class ApiScoringTests(unittest.TestCase):
    def test_risk_band_thresholds_are_stable(self) -> None:
        self.assertEqual(risk_band(0.10), "low")
        self.assertEqual(risk_band(0.40), "medium")
        self.assertEqual(risk_band(0.80), "high")

    def test_scoring_service_returns_probability_and_warnings(self) -> None:
        service = get_scoring_service()

        result = service.score(
            {
                "annual_income": 4_200_000,
                "total_outstanding_debt": 650_000,
                "mobile_banking_logins": 18,
                "online_transfer_frequency": 7,
                "atm_withdrawal_frequency": 2,
                "avg_deposit_amount": 140_000,
                "debit_card_spending": 90_000,
                "loan_application_amount": 300_000,
                "num_open_loans": 1,
                "late_payment_count": 0,
                "gender": "Female",
                "employment_status": "Self-employed",
                "settlement_type": "urban",
                "pavlodar_district": "Pavlodar city",
            }
        )

        self.assertGreaterEqual(result.high_risk_probability, 0.0)
        self.assertLessEqual(result.high_risk_probability, 1.0)
        self.assertIn(result.risk_band, {"low", "medium", "high"})
        self.assertGreater(len(result.top_model_factors), 0)
        self.assertEqual(len(result.scenario_scores), 2)
        self.assertGreaterEqual(result.proxy_sensitivity_delta, 0.0)
        self.assertIsNotNone(result.decision_support)
        self.assertGreater(len(result.decision_support.rationale), 0)
        self.assertGreater(len(result.decision_support.next_steps), 0)

    def test_scoring_factors_are_local_to_application(self) -> None:
        service = get_scoring_service()

        result = service.score(
            {
                "annual_income": 52_000,
                "total_outstanding_debt": 6_500,
                "mobile_banking_logins": 18,
                "online_transfer_frequency": 7,
                "atm_withdrawal_frequency": 2,
                "avg_deposit_amount": 1_400,
                "debit_card_spending": 900,
                "loan_application_amount": 3_000,
                "num_open_loans": 1,
                "late_payment_count": 0,
                "gender": "Female",
                "employment_status": "Self-employed",
                "settlement_type": "urban",
                "pavlodar_district": "Pavlodar city",
            }
        )

        factor_names = {factor["feature"] for factor in result.top_model_factors}
        self.assertNotIn("pavlodar_district_Akkuly", factor_names)
        self.assertGreaterEqual(result.missing_feature_count, 0)

    def test_thin_file_scenario_exposes_proxy_sensitivity(self) -> None:
        service = get_scoring_service()
        base_features = {
            "annual_income": 52_000,
            "total_outstanding_debt": 6_500,
            "mobile_banking_logins": 18,
            "online_transfer_frequency": 7,
            "atm_withdrawal_frequency": 2,
            "avg_deposit_amount": 1_400,
            "debit_card_spending": 900,
            "loan_application_amount": 3_000,
            "num_open_loans": 1,
            "gender": "Female",
            "employment_status": "Self-employed",
            "settlement_type": "urban",
            "pavlodar_district": "Pavlodar city",
        }

        result = service.score({**base_features, "late_payment_count": 5})
        scenarios = {scenario.scenario: scenario for scenario in result.scenario_scores}

        self.assertIn("standard", scenarios)
        self.assertIn("thin_file_without_late_payment_count", scenarios)
        self.assertGreater(result.proxy_sensitivity_delta, 0.2)
        self.assertGreater(
            scenarios["standard"].high_risk_probability,
            scenarios["thin_file_without_late_payment_count"].high_risk_probability,
        )
        self.assertEqual(
            result.decision_support.recommendation_code,
            "manual_review_proxy_sensitive",
        )
        self.assertIn("automatic decline", " ".join(result.decision_support.next_steps))


if __name__ == "__main__":
    unittest.main()
