from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.ablation import ablation_scenarios, run_ablation_study
from microscore.modeling import build_logistic_regression


def _sample_credit_frame(rows: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    credit_risk = np.array([0, 1] * (rows // 2))
    late_payment_count = credit_risk * 2 + rng.integers(0, 2, size=rows)

    return pd.DataFrame(
        {
            "customer_id": [f"CUST_{index:04d}" for index in range(rows)],
            "age": rng.integers(21, 61, size=rows),
            "gender": np.where(np.arange(rows) % 2 == 0, "Female", "Male"),
            "employment_status": np.where(
                np.arange(rows) % 3 == 0,
                "Self-employed",
                "Employed",
            ),
            "annual_income": rng.normal(3_200_000, 450_000, size=rows).clip(500_000),
            "account_age_months": rng.integers(3, 80, size=rows),
            "avg_monthly_balance": rng.normal(180_000, 50_000, size=rows).clip(10_000),
            "num_deposits_per_month": rng.integers(1, 8, size=rows),
            "avg_deposit_amount": rng.normal(75_000, 20_000, size=rows).clip(5_000),
            "debit_card_usage_frequency": rng.integers(2, 40, size=rows),
            "debit_card_spending": rng.normal(120_000, 30_000, size=rows).clip(5_000),
            "mobile_banking_logins": rng.integers(1, 60, size=rows),
            "online_transfer_frequency": rng.integers(0, 25, size=rows),
            "atm_withdrawal_frequency": rng.integers(0, 15, size=rows),
            "credit_score": 720 - credit_risk * 120 + rng.integers(-20, 20, size=rows),
            "num_open_loans": rng.integers(0, 5, size=rows),
            "total_outstanding_debt": rng.normal(420_000, 130_000, size=rows).clip(0),
            "late_payment_count": late_payment_count,
            "loan_default_history": credit_risk,
            "fraud_flag": np.zeros(rows, dtype=int),
            "loan_application_amount": rng.normal(300_000, 80_000, size=rows).clip(20_000),
            "credit_risk": credit_risk,
        }
    )


class AblationStudyTests(unittest.TestCase):
    def test_ablation_scenarios_include_core_research_questions(self) -> None:
        names = {scenario.name for scenario in ablation_scenarios()}

        self.assertIn("all_features_raw", names)
        self.assertIn("no_leakage_baseline", names)
        self.assertIn("no_late_payment_count", names)
        self.assertIn("behavioral_only", names)
        self.assertIn("regional_only", names)
        self.assertIn("behavioral_plus_regional", names)

    def test_run_ablation_study_reports_scenario_metadata(self) -> None:
        table = run_ablation_study(
            frame=_sample_credit_frame(),
            model_factories={
                "Logistic Regression": lambda: build_logistic_regression(11),
            },
            random_state=11,
        )

        self.assertEqual(len(table), len(ablation_scenarios()))
        self.assertIn("delta_test_roc_auc_vs_no_leakage", table.columns)
        self.assertIn("delta_test_brier_score_vs_no_leakage", table.columns)

        all_features = table[table["scenario"] == "all_features_raw"].iloc[0]
        no_late = table[table["scenario"] == "no_late_payment_count"].iloc[0]
        regional_only = table[table["scenario"] == "regional_only"].iloc[0]
        behavioral_plus_regional = table[
            table["scenario"] == "behavioral_plus_regional"
        ].iloc[0]

        self.assertTrue(all_features["includes_leakage_columns"])
        self.assertFalse(no_late["includes_late_payment_count"])
        self.assertTrue(regional_only["uses_regional_context"])
        self.assertTrue(behavioral_plus_regional["uses_regional_context"])
        self.assertFalse(behavioral_plus_regional["includes_leakage_columns"])


if __name__ == "__main__":
    unittest.main()
