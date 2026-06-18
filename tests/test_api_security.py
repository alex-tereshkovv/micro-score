from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.rate_limit import LoginRateLimiter
from microscore_api.security import password_policy_violations


class ApiSecurityTests(unittest.TestCase):
    def test_password_policy_rejects_common_and_incomplete_passwords(self) -> None:
        self.assertIn("avoid a common password", password_policy_violations("password123"))
        self.assertIn("include an uppercase letter", password_policy_violations("longpassword1!"))
        self.assertIn("include a number", password_policy_violations("LongPassword!"))
        self.assertEqual(password_policy_violations("StrongPassword1!"), [])

    def test_login_rate_limiter_blocks_and_resets_attempts(self) -> None:
        current_time = [100.0]
        limiter = LoginRateLimiter(
            max_attempts=3,
            window_seconds=60,
            block_seconds=120,
            clock=lambda: current_time[0],
        )

        self.assertEqual(limiter.record_failure("client:user"), 0)
        self.assertEqual(limiter.record_failure("client:user"), 0)
        self.assertEqual(limiter.record_failure("client:user"), 120)
        self.assertEqual(limiter.retry_after("client:user"), 120)

        current_time[0] += 121
        self.assertEqual(limiter.retry_after("client:user"), 0)
        self.assertEqual(limiter.record_failure("client:user"), 0)
        limiter.record_success("client:user")
        self.assertEqual(limiter.retry_after("client:user"), 0)


if __name__ == "__main__":
    unittest.main()
