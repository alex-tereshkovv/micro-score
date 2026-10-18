from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


DEFAULT_REQUESTS = 160
DEFAULT_CONCURRENCY = 8
DEFAULT_P95_BUDGET_MS = 750.0
DEFAULT_MIN_THROUGHPUT_RPS = 15.0
DEMO_PASSWORD = "password123"
DEMO_MFA_CODE = "246810"


class PerformanceFailure(AssertionError):
    pass


def performance_contract() -> dict[str, object]:
    return {
        "mode": "http-performance-smoke-dry-run",
        "requests": DEFAULT_REQUESTS,
        "concurrency": DEFAULT_CONCURRENCY,
        "p95_budget_ms": DEFAULT_P95_BUDGET_MS,
        "minimum_throughput_rps": DEFAULT_MIN_THROUGHPUT_RPS,
        "server_error_rate_budget": 0.0,
        "request_id_propagation": True,
        "server_timing_required": True,
        "workload_routes": ["/health", "/organizations", "/mfi/applications"],
        "production_capacity_claim": False,
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return round(ordered[index], 3)


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any, dict[str, str], float]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if request_id:
        headers["X-Request-ID"] = request_id
    request = urllib.request.Request(
        f"{base_url}{path}", data=data, headers=headers, method=method
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status_code = int(response.status)
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status_code = int(exc.code)
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
    duration_ms = (time.perf_counter() - started) * 1000
    decoded: Any = None
    if body:
        text = body.decode("utf-8")
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = text
    return status_code, decoded, response_headers, duration_ms


def _wait_for_api(base_url: str, process: subprocess.Popen[Any]) -> None:
    deadline = time.time() + 30
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            raise PerformanceFailure(f"uvicorn exited early with {process.returncode}")
        try:
            status_code, payload, _, _ = _request(base_url, "GET", "/health")
            if status_code == 200 and payload.get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001 - bounded startup retry.
            last_error = exc
        time.sleep(0.25)
    raise PerformanceFailure(f"Timed out waiting for API: {last_error}")


def _start_api(db_path: Path | None, port: int) -> subprocess.Popen[Any]:
    environment = os.environ.copy()
    if db_path is not None:
        environment["MICROSCORE_STORAGE_BACKEND"] = "sqlite"
        environment["MICROSCORE_API_DB_PATH"] = str(db_path)
    environment["PYTHONPATH"] = (
        str(SRC_ROOT)
        if not environment.get("PYTHONPATH")
        else f"{SRC_ROOT}{os.pathsep}{environment['PYTHONPATH']}"
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "microscore_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def _terminate(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=8)


def _seed_database(db_path: Path | None) -> dict[str, Any]:
    if db_path is not None:
        os.environ["MICROSCORE_STORAGE_BACKEND"] = "sqlite"
        os.environ["MICROSCORE_API_DB_PATH"] = str(db_path)
        from microscore_api.database import MicroScoreRepository
        from microscore_api.seed import seed_demo_data

        return seed_demo_data(MicroScoreRepository(db_path))

    from microscore_api.database import create_repository
    from microscore_api.seed import seed_demo_data

    return seed_demo_data(create_repository())


def _login(base_url: str, email: str) -> str:
    status_code, payload, _, _ = _request(
        base_url,
        "POST",
        "/auth/login",
        payload={
            "email": email,
            "password": DEMO_PASSWORD,
            "mfa_code": DEMO_MFA_CODE,
        },
    )
    if status_code != 200:
        raise PerformanceFailure(f"Login for {email} returned {status_code}: {payload}")
    return str(payload["access_token"])


def _run_workload(
    *,
    base_url: str,
    analyst_token: str,
    request_count: int,
    concurrency: int,
) -> tuple[list[float], float, list[str]]:
    workload = (
        ("/health", None),
        ("/organizations", None),
        ("/mfi/applications", analyst_token),
    )

    def execute(index: int) -> tuple[float, str | None]:
        path, token = workload[index % len(workload)]
        request_id = f"perf-{index:06d}-request"
        status_code, _, headers, duration_ms = _request(
            base_url,
            "GET",
            path,
            token=token,
            request_id=request_id,
        )
        if status_code != 200:
            return duration_ms, f"{path} returned {status_code}"
        if headers.get("x-request-id") != request_id:
            return duration_ms, f"{path} did not preserve X-Request-ID"
        if not headers.get("server-timing", "").startswith("app;dur="):
            return duration_ms, f"{path} did not expose Server-Timing"
        return duration_ms, None

    latencies: list[float] = []
    errors: list[str] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(execute, index) for index in range(request_count)]
        for future in as_completed(futures):
            duration_ms, error = future.result()
            latencies.append(duration_ms)
            if error:
                errors.append(error)
    return latencies, time.perf_counter() - started, errors


def run_performance_smoke(
    *,
    request_count: int,
    concurrency: int,
    p95_budget_ms: float,
    minimum_throughput_rps: float,
) -> dict[str, Any]:
    backend = os.environ.get("MICROSCORE_STORAGE_BACKEND", "sqlite").strip().lower()
    if backend not in {"sqlite", "postgresql", "postgres"}:
        raise PerformanceFailure(f"Unsupported storage backend: {backend}")
    if backend in {"postgresql", "postgres"} and not os.environ.get(
        "MICROSCORE_DATABASE_URL", ""
    ).strip():
        raise PerformanceFailure("MICROSCORE_DATABASE_URL is required for PostgreSQL")

    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    db_path: Path | None = None
    if backend == "sqlite":
        temporary_directory = tempfile.TemporaryDirectory(
            prefix="microscore-performance-"
        )
        db_path = Path(temporary_directory.name) / "performance.sqlite3"
    seed_result = _seed_database(db_path)
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    process = _start_api(db_path, port)
    try:
        _wait_for_api(base_url, process)
        analyst_token = _login(base_url, "analyst@test.com")
        admin_token = _login(base_url, "admin@test.com")
        for warmup_index in range(12):
            status_code, _, _, _ = _request(
                base_url,
                "GET",
                "/mfi/applications",
                token=analyst_token,
                request_id=f"warmup-{warmup_index:04d}",
            )
            if status_code != 200:
                raise PerformanceFailure(f"Warmup request returned {status_code}")

        latencies, elapsed_seconds, errors = _run_workload(
            base_url=base_url,
            analyst_token=analyst_token,
            request_count=request_count,
            concurrency=concurrency,
        )
        readiness_status, readiness, _, _ = _request(
            base_url,
            "GET",
            "/admin/operations/runtime-readiness",
            token=admin_token,
        )
        if readiness_status != 200:
            raise PerformanceFailure(
                f"Runtime readiness returned {readiness_status}: {readiness}"
            )
    finally:
        _terminate(process)
        if temporary_directory is not None:
            temporary_directory.cleanup()

    p95_ms = _percentile(latencies, 0.95)
    p99_ms = _percentile(latencies, 0.99)
    throughput_rps = request_count / elapsed_seconds if elapsed_seconds else 0.0
    if errors:
        raise PerformanceFailure(
            f"{len(errors)} workload request(s) failed: {errors[:5]}"
        )
    if p95_ms > p95_budget_ms:
        raise PerformanceFailure(
            f"Client p95 {p95_ms} ms exceeded budget {p95_budget_ms} ms"
        )
    if throughput_rps < minimum_throughput_rps:
        raise PerformanceFailure(
            f"Throughput {throughput_rps:.3f} rps was below budget "
            f"{minimum_throughput_rps:.3f} rps"
        )
    if readiness["server_error_count"] != 0:
        raise PerformanceFailure("Runtime telemetry recorded server errors")
    if readiness["status"] != "ready":
        raise PerformanceFailure(
            f"Runtime readiness budget status was {readiness['status']!r}"
        )

    return {
        "mode": "http-performance-smoke",
        "storage_backend": "postgresql" if backend in {"postgresql", "postgres"} else "sqlite",
        "requests": request_count,
        "concurrency": concurrency,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_rps": round(throughput_rps, 3),
        "client_latency_ms": {
            "average": round(sum(latencies) / len(latencies), 3),
            "p50": _percentile(latencies, 0.50),
            "p95": p95_ms,
            "p99": p99_ms,
            "max": round(max(latencies), 3),
        },
        "budgets": {
            "p95_latency_ms": p95_budget_ms,
            "minimum_throughput_rps": minimum_throughput_rps,
            "server_error_rate": 0.0,
        },
        "request_id_propagation": True,
        "server_timing_present": True,
        "runtime_request_count": readiness["request_count"],
        "runtime_p95_ms": readiness["latency_ms"]["p95_ms"],
        "runtime_server_error_rate": readiness["server_error_rate"],
        "seeded_applications": len(seed_result["demo_application_ids"]),
        "production_capacity_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded concurrent HTTP performance and telemetry smoke test."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--p95-budget-ms", type=float, default=DEFAULT_P95_BUDGET_MS)
    parser.add_argument(
        "--min-throughput-rps",
        type=float,
        default=DEFAULT_MIN_THROUGHPUT_RPS,
    )
    arguments = parser.parse_args()
    if arguments.dry_run:
        print(json.dumps(performance_contract(), indent=2, sort_keys=True))
        return 0
    if arguments.requests < 1 or arguments.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")
    if arguments.concurrency > arguments.requests:
        parser.error("--concurrency cannot exceed --requests")

    try:
        result = run_performance_smoke(
            request_count=arguments.requests,
            concurrency=arguments.concurrency,
            p95_budget_ms=arguments.p95_budget_ms,
            minimum_throughput_rps=arguments.min_throughput_rps,
        )
    except Exception as exc:
        print(
            f"::error title=HTTP performance smoke failed::{exc}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
