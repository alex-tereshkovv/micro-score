from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from microscore_api.database import MicroScoreRepository
from microscore_api.seed import DEMO_APPLICATION_ID, DEMO_PASSWORD, DEMO_USERS, seed_demo_data


class ApiSeedTests(unittest.TestCase):
    def test_seed_demo_data_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repository = MicroScoreRepository(Path(tempdir) / "seed-test.sqlite3")

            first = seed_demo_data(repository)
            second = seed_demo_data(repository)

            self.assertEqual(first["demo_password"], DEMO_PASSWORD)
            self.assertEqual(len(first["created_users"]), len(DEMO_USERS))
            self.assertEqual(second["demo_application_status"], "already_exists")
            self.assertIsNotNone(repository.get_application(DEMO_APPLICATION_ID))
            self.assertEqual(repository.get_user("analyst@test.com")["role"], "mfi_analyst")


if __name__ == "__main__":
    unittest.main()
