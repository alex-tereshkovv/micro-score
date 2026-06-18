from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.privacy import find_forbidden_signal_paths


class ApiPrivacyTests(unittest.TestCase):
    def test_safe_behavioral_fields_are_allowed(self) -> None:
        payload = {
            "annual_income": 4_200_000,
            "mobile_banking_logins": 18,
            "employment_status": "Self-employed",
            "late_payment_count": 0,
        }

        self.assertEqual(find_forbidden_signal_paths(payload), [])

    def test_sensitive_fields_are_reported_with_nested_paths(self) -> None:
        payload = {
            "iin": "demo-value",
            "profile": {
                "passport_number": "demo-value",
                "documents": [{"raw_bank_statement": "demo-value"}],
            },
        }

        self.assertEqual(
            find_forbidden_signal_paths(payload),
            [
                "behavioral_signals.iin",
                "behavioral_signals.profile.documents[0].raw_bank_statement",
                "behavioral_signals.profile.passport_number",
            ],
        )


if __name__ == "__main__":
    unittest.main()
