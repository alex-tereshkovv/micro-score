from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional app dependency.
    TestClient = None

from microscore_api.observability import (  # noqa: E402
    MAX_GLOBAL_SAMPLES,
    MAX_ROUTE_SERIES,
    RuntimeMetrics,
    safe_request_id,
    safe_route_label,
)

if TestClient is not None:
    from microscore_api.database import MicroScoreRepository
    from microscore_api.main import app, get_repository
    from microscore_api.security import hash_password


class RuntimeMetricsTests(unittest.TestCase):
    def test_metrics_are_bounded_and_report_percentiles_and_error_classes(self) -> None:
        metrics = RuntimeMetrics()
        for index in range(MAX_GLOBAL_SAMPLES + 25):
            metrics.begin_request()
            metrics.complete_request(
                method="GET",
                route="/health",
                status_code=503 if index == 0 else 200,
                duration_ms=float(index % 100),
            )

        snapshot = metrics.snapshot(
            p95_latency_budget_ms=50.0,
            server_error_rate_budget=0.0,
        )
        self.assertEqual(snapshot["request_count"], MAX_GLOBAL_SAMPLES + 25)
        self.assertEqual(snapshot["latency_ms"]["sample_count"], MAX_GLOBAL_SAMPLES)
        self.assertEqual(snapshot["server_error_count"], 1)
        self.assertEqual(snapshot["status"], "attention")
        self.assertEqual(snapshot["budget_checks"][0]["status"], "fail")
        self.assertEqual(snapshot["budget_checks"][1]["status"], "fail")
        self.assertEqual(snapshot["top_routes"][0]["route"], "/health")
        self.assertFalse(snapshot["production_ready"])

        bounded_routes = RuntimeMetrics()
        for index in range(MAX_ROUTE_SERIES + 10):
            bounded_routes.begin_request()
            bounded_routes.complete_request(
                method="GET",
                route=f"/route/{index}",
                status_code=200,
                duration_ms=1.0,
            )
        self.assertLessEqual(len(bounded_routes._routes), MAX_ROUTE_SERIES + 1)

    def test_request_id_and_route_labels_reject_unsafe_cardinality(self) -> None:
        self.assertEqual(safe_request_id("review-12345678"), "review-12345678")
        generated = safe_request_id("unsafe request id with spaces")
        self.assertRegex(generated, r"^[0-9a-f]{32}$")
        self.assertEqual(
            safe_route_label(
                "/applications/123e4567-e89b-12d3-a456-426614174000/timeline"
            ),
            "/unmatched",
        )
        self.assertEqual(
            safe_route_label("/ignored", "/applications/{application_id}"),
            "/applications/{application_id}",
        )
        self.assertEqual(
            safe_route_label("/admin/users/private@example.com/disable"),
            "/unmatched",
        )


@unittest.skipIf(TestClient is None, "FastAPI app dependencies are not installed")
class RuntimeReadinessApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = MicroScoreRepository(
            Path(self.tempdir.name) / "observability.sqlite3"
        )
        self.repository.create_user(
            "admin-observability@test.com",
            hash_password("StrongPassword1!"),
            "admin",
        )
        self.repository.attest_user_mfa(
            "admin-observability@test.com",
            "admin-observability@test.com",
            "prototype_mfa_code",
        )
        app.dependency_overrides[get_repository] = lambda: self.repository
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.tempdir.cleanup()

    def _admin_token(self) -> str:
        response = self.client.post(
            "/auth/login",
            json={
                "email": "admin-observability@test.com",
                "password": "StrongPassword1!",
                "mfa_code": "246810",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_middleware_propagates_request_id_and_emits_safe_structured_log(self) -> None:
        with self.assertLogs("microscore.request", level="INFO") as captured:
            response = self.client.get(
                "/health?borrower=private@example.com",
                headers={"X-Request-ID": "review-12345678"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "review-12345678")
        self.assertTrue(response.headers["server-timing"].startswith("app;dur="))
        event = json.loads(captured.records[-1].getMessage())
        self.assertEqual(event["event"], "http_request_completed")
        self.assertEqual(event["route"], "/health")
        self.assertNotIn("private@example.com", captured.output[-1])
        self.assertNotIn("borrower", captured.output[-1])

    def test_runtime_readiness_is_admin_only_and_exposes_bounded_metrics(self) -> None:
        unauthorized = self.client.get("/admin/operations/runtime-readiness")
        self.assertEqual(unauthorized.status_code, 401)
        token = self._admin_token()
        response = self.client.get(
            "/admin/operations/runtime-readiness",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn(payload["status"], {"ready", "attention"})
        self.assertGreaterEqual(payload["request_count"], 2)
        self.assertLessEqual(payload["latency_ms"]["sample_count"], MAX_GLOBAL_SAMPLES)
        self.assertEqual(len(payload["budget_checks"]), 2)
        self.assertIn("p95_latency_ms", payload["budgets"])
        self.assertIn("server_error_rate", payload["budgets"])
        self.assertFalse(payload["production_ready"])
        self.assertIn("Process-local", payload["limitation"])


class PerformanceSmokeContractTests(unittest.TestCase):
    def test_performance_smoke_dry_run_exposes_explicit_budgets(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "http-performance-smoke.py"),
                "--dry-run",
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "http-performance-smoke-dry-run")
        self.assertEqual(payload["requests"], 160)
        self.assertEqual(payload["concurrency"], 8)
        self.assertEqual(payload["p95_budget_ms"], 750.0)
        self.assertEqual(payload["minimum_throughput_rps"], 15.0)
        self.assertTrue(payload["request_id_propagation"])
        self.assertTrue(payload["server_timing_required"])
        self.assertFalse(payload["production_capacity_claim"])


if __name__ == "__main__":
    unittest.main()
