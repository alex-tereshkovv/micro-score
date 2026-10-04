from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeploymentCandidateTests(unittest.TestCase):
    def test_compose_defines_health_gated_full_stack(self) -> None:
        compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")

        for service in ["postgres:", "migrate:", "seed:", "api:", "web:"]:
            self.assertIn(service, compose)
        self.assertIn("postgres:16-alpine", compose)
        self.assertIn("python\", \"-m\", \"microscore_api.migrate", compose)
        self.assertIn("service_completed_successfully", compose)
        self.assertIn("service_healthy", compose)
        self.assertIn("MICROSCORE_STORAGE_BACKEND: postgresql", compose)
        self.assertIn("read_only: true", compose)
        self.assertNotIn('"5432:5432"', compose)

    def test_images_run_application_processes_as_non_root(self) -> None:
        api_dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        web_dockerfile = (PROJECT_ROOT / "apps" / "web" / "Dockerfile").read_text(
            encoding="utf-8"
        )

        self.assertIn("FROM python:3.12-slim", api_dockerfile)
        self.assertIn("USER microscore", api_dockerfile)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", api_dockerfile)
        self.assertIn("/health", api_dockerfile)
        self.assertIn("nginxinc/nginx-unprivileged:alpine", web_dockerfile)
        self.assertIn("--chown=101:101", web_dockerfile)

    def test_compose_example_labels_credentials_as_local_only(self) -> None:
        example = (PROJECT_ROOT / ".env.compose.example").read_text(encoding="utf-8")
        dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

        self.assertIn("Local synthetic-demo configuration only", example)
        self.assertIn("replace-for-any-shared-environment", example)
        self.assertIn(".env", dockerignore)
        self.assertIn("data/app", dockerignore)


if __name__ == "__main__":
    unittest.main()
