from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.modeling import build_logistic_regression
from microscore.robustness import (
    BASELINE_SCENARIO,
    THIN_FILE_SCENARIO,
    apply_covariate_shift,
    bootstrap_metric_intervals,
    run_robustness_suite,
)


def _sample_credit_frame(rows: int = 160) -> pd.DataFrame:
    rng = np.random.default_rng(71)
    credit_risk = np.array([0, 1] * (rows // 2))
    return pd.DataFrame(
        {
            "customer_id": [f"ROB_{index:04d}" for index in range(rows)],
            "age": rng.integers(21, 66, size=rows),
            "gender": np.where(np.arange(rows) % 2 == 0, "Female", "Male"),
            "employment_status": np.where(
                np.arange(rows) % 3 == 0,
                "Employed",
                "Self-employed",
            ),
            "annual_income": rng.normal(3_200_000, 500_000, size=rows).clip(500_000),
            "avg_monthly_balance": rng.normal(180_000, 55_000, size=rows).clip(5_000),
            "avg_deposit_amount": rng.normal(75_000, 18_000, size=rows).clip(5_000),
            "debit_card_spending": rng.normal(120_000, 35_000, size=rows).clip(5_000),
            "mobile_banking_logins": rng.integers(1, 60, size=rows),
            "online_transfer_frequency": rng.integers(0, 25, size=rows),
            "atm_withdrawal_frequency": rng.integers(0, 15, size=rows),
            "credit_score": 720 - credit_risk * 120,
            "num_open_loans": rng.integers(0, 5, size=rows),
            "total_outstanding_debt": rng.normal(420_000, 140_000, size=rows).clip(0),
            "late_payment_count": credit_risk * 3 + rng.integers(0, 2, size=rows),
            "loan_default_history": credit_risk,
            "fraud_flag": np.zeros(rows, dtype=int),
            "loan_application_amount": rng.normal(300_000, 90_000, size=rows).clip(20_000),
            "credit_risk": credit_risk,
        }
    )


class RobustnessTests(unittest.TestCase):
    def test_bootstrap_intervals_are_deterministic_and_contain_estimate(self) -> None:
        labels = np.array([0, 1] * 50)
        probabilities = np.linspace(0.05, 0.95, 100)
        first = bootstrap_metric_intervals(labels, probabilities, iterations=100, random_state=9)
        second = bootstrap_metric_intervals(labels, probabilities, iterations=100, random_state=9)

        pd.testing.assert_frame_equal(first, second)
        self.assertTrue((first["ci_lower"] <= first["point_estimate"]).all())
        self.assertTrue((first["point_estimate"] <= first["ci_upper"]).all())

    def test_covariate_shift_is_explicit_and_does_not_mutate_source(self) -> None:
        frame = _sample_credit_frame()
        original = frame.copy(deep=True)
        shifted = apply_covariate_shift(frame, "affordability_pressure")

        pd.testing.assert_frame_equal(frame, original)
        self.assertTrue((shifted["annual_income"] < frame["annual_income"]).all())
        self.assertTrue(
            (shifted["total_outstanding_debt"] >= frame["total_outstanding_debt"]).all()
        )

    def test_suite_reports_repeated_splits_intervals_and_shift(self) -> None:
        factories = {"Logistic Regression": lambda: build_logistic_regression(71)}
        report = run_robustness_suite(
            _sample_credit_frame(),
            model_factories=factories,
            random_states=(7, 19, 42),
            bootstrap_iterations=100,
            random_state=42,
        )

        self.assertEqual(len(report.split_runs), 6)
        self.assertEqual(
            set(report.split_summary["scenario"]),
            {BASELINE_SCENARIO, THIN_FILE_SCENARIO},
        )
        self.assertEqual(set(report.bootstrap_intervals["metric"]), {"roc_auc", "brier_score"})
        self.assertIn("classification_flip_rate", report.covariate_shift.columns)
        self.assertEqual(
            set(report.covariate_shift["scenario"]),
            {
                "baseline",
                "digital_access_contraction",
                "affordability_pressure",
                "repayment_history_missing",
            },
        )

    def test_bootstrap_rejects_single_class_targets(self) -> None:
        with self.assertRaisesRegex(ValueError, "both target classes"):
            bootstrap_metric_intervals(
                np.zeros(20, dtype=int),
                np.full(20, 0.1),
                iterations=50,
            )


if __name__ == "__main__":
    unittest.main()
