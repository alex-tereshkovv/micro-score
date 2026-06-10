from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore.policy import ThresholdPolicy
from microscore_api.analytics import policy_analytics


class ApiAnalyticsTests(unittest.TestCase):
    def test_policy_analytics_summarizes_live_scored_applications(self) -> None:
        applications = [
            self._application(0.10, "Female", "Self-employed", "Pavlodar city", "urban"),
            self._application(0.40, "Male", "Employed", "Bayanaul", "rural"),
            self._application(0.80, "Female", "Self-employed", "Bayanaul", "rural"),
            {"score_result": None, "behavioral_signals": {}},
        ]

        result = policy_analytics(
            applications,
            policies=(
                ThresholdPolicy(
                    name="test_policy",
                    approve_threshold=0.20,
                    decline_threshold=0.70,
                    description="Test policy",
                ),
            ),
        )

        self.assertEqual(result["scored_application_count"], 3)
        policy_row = result["policies"][0]
        self.assertEqual(policy_row["auto_approve_count"], 1)
        self.assertEqual(policy_row["manual_review_count"], 1)
        self.assertEqual(policy_row["auto_decline_count"], 1)
        self.assertAlmostEqual(policy_row["auto_approval_rate"], 1 / 3)
        self.assertEqual(policy_row["predicted_high_risk_auto_approved_count"], 0)

        segment_rows = {
            (row["segment_feature"], row["segment_value"]): row
            for row in result["segments"]
        }
        self.assertAlmostEqual(
            segment_rows[("gender", "Female")]["auto_decline_rate"],
            0.5,
        )
        self.assertAlmostEqual(
            segment_rows[("settlement_type", "rural")]["manual_review_rate"],
            0.5,
        )

    @staticmethod
    def _application(
        probability: float,
        gender: str,
        employment_status: str,
        district: str,
        settlement_type: str,
    ) -> dict[str, object]:
        return {
            "district": district,
            "settlement_type": settlement_type,
            "behavioral_signals": {
                "gender": gender,
                "employment_status": employment_status,
            },
            "score_result": {
                "high_risk_probability": probability,
            },
        }


if __name__ == "__main__":
    unittest.main()
