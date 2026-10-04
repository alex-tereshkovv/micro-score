from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from microscore_api.database import MicroScoreRepository, create_repository
from microscore_api.migrate import main as migrate_main
from microscore_api.postgres_runtime import PostgresRuntimeRepository


class PostgresRuntimeTests(unittest.TestCase):
    def test_safe_database_label_never_exposes_credentials(self) -> None:
        repository = PostgresRuntimeRepository(
            "postgresql://secret-user:super-secret@db.example:5432/microscore",
            connection_factory=lambda: None,
            initialize=False,
        )

        self.assertEqual(
            repository.database_label,
            "postgresql://db.example:5432/microscore",
        )
        self.assertNotIn("secret-user", repository.database_label)
        self.assertNotIn("super-secret", repository.database_label)

    def test_invalid_database_url_fails_without_echoing_secret(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "postgresql:// URL") as raised:
            PostgresRuntimeRepository(
                "sqlite:///super-secret.sqlite3",
                connection_factory=lambda: None,
                initialize=False,
            )

        self.assertNotIn("super-secret", str(raised.exception))

    def test_repository_factory_keeps_sqlite_as_default(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "runtime.sqlite3"
            with patch.dict(os.environ, {}, clear=True):
                repository = create_repository(path)

        self.assertIsInstance(repository, MicroScoreRepository)
        self.assertEqual(repository.storage_backend, "sqlite")

    def test_repository_factory_selects_postgresql_explicitly(self) -> None:
        sentinel = object()
        configured = {
            "MICROSCORE_STORAGE_BACKEND": "postgresql",
            "MICROSCORE_DATABASE_URL": "postgresql://db.example/microscore",
        }
        with patch.dict(os.environ, configured, clear=True), patch(
            "microscore_api.postgres_runtime.PostgresRuntimeRepository.from_environment",
            return_value=sentinel,
        ) as factory:
            repository = create_repository()

        self.assertIs(repository, sentinel)
        factory.assert_called_once_with()

    def test_migration_entrypoint_reports_safe_runtime_evidence(self) -> None:
        repository = unittest.mock.MagicMock()
        repository.storage_backend = "postgresql"
        repository.database_label = "postgresql://db.example/microscore"
        repository.apply_migrations.return_value = ["0001_initial_schema.sql"]
        repository.postgresql_migration_readiness.return_value = {
            "present_table_count": 11,
            "required_table_count": 11,
            "production_ready": False,
        }
        configured = {
            "MICROSCORE_STORAGE_BACKEND": "postgresql",
            "MICROSCORE_DATABASE_URL": "postgresql://secret:password@db.example/microscore",
        }
        output = StringIO()
        with patch.dict(os.environ, configured, clear=True), patch(
            "microscore_api.migrate.PostgresRuntimeRepository",
            return_value=repository,
        ), redirect_stdout(output):
            result = migrate_main()

        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["backend"], "postgresql")
        self.assertFalse(payload["production_ready"])
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("password", output.getvalue())
        repository.apply_migrations.assert_called_once_with()
        repository.initialize.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
