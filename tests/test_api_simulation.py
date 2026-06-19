from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.simulation import simulate_portfolio


def scored_application(
    application_id: str,
    probability: float,
    amount: float,
    *,
    model_version: str = "research-v0.1",
) -> dict[str, object]:
    return {
        "id": application_id,
        "requested_amount": amount,
        "score_result": {
            "high_risk_probability": probability,
            "model_version": model_version,
        },
    }


class PortfolioSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.applications = [
            scored_application("a-1", 0.08, 180_000),
            scored_application("a-2", 0.18, 250_000),
            scored_application("a-3", 0.32, 300_000),
            scored_application("a-4", 0.48, 420_000),
            scored_application("a-5", 0.66, 500_000),
            scored_application("a-6", 0.82, 600_000),
            {"id": "unscored", "requested_amount": 200_000, "score_result": None},
        ]

    def test_seeded_simulation_is_reproducible(self) -> None:
        first = simulate_portfolio(
            self.applications,
            iterations=1_000,
            seed=1234,
        )
        second = simulate_portfolio(
            self.applications,
            iterations=1_000,
            seed=1234,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["application_count"], 7)
        self.assertEqual(first["scored_application_count"], 6)
        self.assertEqual(first["unscored_application_count"], 1)
        self.assertTrue(any("excluded" in warning for warning in first["warnings"]))
        self.assertTrue(any("Operating cost is zero" in warning for warning in first["warnings"]))
        self.assertEqual(first["model_versions"], ["research-v0.1"])
        self.assertEqual(first["assumptions"]["seed"], 1234)

    def test_stress_scenarios_increase_defaults_and_reduce_result(self) -> None:
        result = simulate_portfolio(
            self.applications,
            iterations=2_000,
            seed=77,
        )
        scenarios = {row["scenario"]: row for row in result["scenarios"]}

        self.assertLessEqual(
            scenarios["baseline"]["mean_stressed_probability"],
            scenarios["adverse"]["mean_stressed_probability"],
        )
        self.assertLessEqual(
            scenarios["adverse"]["mean_stressed_probability"],
            scenarios["severe"]["mean_stressed_probability"],
        )
        self.assertLessEqual(
            scenarios["baseline"]["default_count"]["mean"],
            scenarios["adverse"]["default_count"]["mean"],
        )
        self.assertLessEqual(
            scenarios["adverse"]["default_count"]["mean"],
            scenarios["severe"]["default_count"]["mean"],
        )
        self.assertGreaterEqual(
            scenarios["baseline"]["portfolio_result"]["mean"],
            scenarios["adverse"]["portfolio_result"]["mean"],
        )
        self.assertGreaterEqual(
            scenarios["adverse"]["portfolio_result"]["mean"],
            scenarios["severe"]["portfolio_result"]["mean"],
        )
        for scenario in scenarios.values():
            self.assertGreaterEqual(scenario["probability_of_loss"], 0.0)
            self.assertLessEqual(scenario["probability_of_loss"], 1.0)
            self.assertLessEqual(
                scenario["portfolio_result"]["p05"],
                scenario["portfolio_result"]["p50"],
            )
            self.assertLessEqual(
                scenario["portfolio_result"]["p50"],
                scenario["portfolio_result"]["p95"],
            )

    def test_manual_review_rate_controls_simulated_book(self) -> None:
        review_only = [
            scored_application("r-1", 0.45, 200_000),
            scored_application("r-2", 0.50, 300_000),
        ]

        none_approved = simulate_portfolio(
            review_only,
            iterations=200,
            scenarios=("baseline",),
            review_approval_rate=0.0,
        )
        all_approved = simulate_portfolio(
            review_only,
            iterations=200,
            scenarios=("baseline",),
            review_approval_rate=1.0,
        )

        self.assertEqual(
            none_approved["scenarios"][0]["approved_count"]["mean"],
            0.0,
        )
        self.assertEqual(
            all_approved["scenarios"][0]["approved_count"]["mean"],
            2.0,
        )

    def test_model_versions_and_policy_are_explicit(self) -> None:
        mixed = [
            scored_application("old", 0.2, 200_000, model_version="research-v0.1"),
            scored_application("new", 0.3, 300_000, model_version="research-v0.2"),
        ]
        result = simulate_portfolio(
            mixed,
            iterations=300,
            policy_name="lender_protective",
            scenarios=("baseline", "severe"),
        )

        self.assertEqual(result["model_versions"], ["research-v0.1", "research-v0.2"])
        self.assertTrue(any("multiple model versions" in warning for warning in result["warnings"]))
        self.assertEqual(result["policy"]["name"], "lender_protective")
        self.assertEqual(
            [row["scenario"] for row in result["scenarios"]],
            ["baseline", "severe"],
        )
        self.assertIn("Scenario-planning output only", result["note"])

    def test_invalid_configuration_and_empty_portfolio_fail_cleanly(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one scored application"):
            simulate_portfolio(
                [{"id": "unscored", "requested_amount": 10_000}],
                iterations=100,
            )
        with self.assertRaisesRegex(ValueError, "Unknown stress scenarios"):
            simulate_portfolio(
                self.applications,
                iterations=100,
                scenarios=("fantasy",),
            )
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            simulate_portfolio(
                self.applications,
                iterations=100,
                loss_given_default=1.2,
            )
        with self.assertRaisesRegex(ValueError, "workload is too large"):
            simulate_portfolio(
                [scored_application("large", 0.2, 100_000)],
                iterations=20_000_001,
                scenarios=("baseline",),
            )


if __name__ == "__main__":
    unittest.main()
