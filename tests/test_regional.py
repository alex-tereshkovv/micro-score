from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.regional import add_pavlodar_regional_context, district_profile_table, regional_summary


class RegionalSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "annual_income": [1000.0, 2000.0, 3000.0, 4000.0],
                "avg_monthly_balance": [100.0, 200.0, 300.0, 400.0],
                "mobile_banking_logins": [2, 4, 6, 8],
                "online_transfer_frequency": [1, 2, 3, 4],
                "atm_withdrawal_frequency": [4, 3, 2, 1],
                "loan_application_amount": [500.0, 600.0, 700.0, 800.0],
                "credit_risk": [0, 1, 0, 1],
            }
        )

    def test_profile_weights_are_normalized_by_simulation(self) -> None:
        profiles = district_profile_table()

        self.assertGreater(len(profiles), 5)
        self.assertAlmostEqual(profiles["base_weight"].sum(), 1.0)

    def test_regional_context_is_reproducible(self) -> None:
        first = add_pavlodar_regional_context(self.frame, random_state=7)
        second = add_pavlodar_regional_context(self.frame, random_state=7)

        self.assertEqual(first["pavlodar_district"].tolist(), second["pavlodar_district"].tolist())
        self.assertIn("financial_access_gap", first.columns)
        self.assertIn("rural_flag", first.columns)

    def test_regional_summary_requires_context_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "Regional columns"):
            regional_summary(self.frame)

        enriched = add_pavlodar_regional_context(self.frame, random_state=7)
        summary = regional_summary(enriched)
        self.assertIn("high_risk_rate", summary.columns)


if __name__ == "__main__":
    unittest.main()
