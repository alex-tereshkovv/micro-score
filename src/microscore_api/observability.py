"""Bounded, credential-safe runtime telemetry for the Senim Risk prototype."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from threading import Lock
import time
from typing import Any
from uuid import uuid4


DEFAULT_P95_LATENCY_BUDGET_MS = 750.0
DEFAULT_SERVER_ERROR_RATE_BUDGET = 0.01
MAX_GLOBAL_SAMPLES = 4096
MAX_ROUTE_SAMPLES = 512
MAX_ROUTE_SERIES = 128
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_request_id(value: str | None) -> str:
    candidate = (value or "").strip()
    if REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


def safe_route_label(path: str, route_template: str | None = None) -> str:
    template = (route_template or "").strip()
    if template.startswith("/") and len(template) <= 160:
        return template
    # Without a framework route template, even a short path segment can be an
    # email, token, or attacker-controlled cardinality source. Collapse it.
    return "/unmatched" if path.startswith("/") else "/unknown"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[rank], 3)


def _latency_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {
            "sample_count": 0,
            "min_ms": 0.0,
            "average_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }
    return {
        "sample_count": len(values),
        "min_ms": round(min(values), 3),
        "average_ms": round(sum(values) / len(values), 3),
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "max_ms": round(max(values), 3),
    }


@dataclass
class RouteMetrics:
    request_count: int = 0
    client_error_count: int = 0
    server_error_count: int = 0
    latency_samples: deque[float] = field(
        default_factory=lambda: deque(maxlen=MAX_ROUTE_SAMPLES)
    )


class RuntimeMetrics:
    """Process-local metrics with fixed memory bounds and no request payload data."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._started_monotonic = time.monotonic()
        self._started_at = utc_now_iso()
        self._in_flight = 0
        self._request_count = 0
        self._client_error_count = 0
        self._server_error_count = 0
        self._status_classes: defaultdict[str, int] = defaultdict(int)
        self._latency_samples: deque[float] = deque(maxlen=MAX_GLOBAL_SAMPLES)
        self._routes: dict[tuple[str, str], RouteMetrics] = {}

    def begin_request(self) -> None:
        with self._lock:
            self._in_flight += 1

    def complete_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        normalized_method = method.upper()[:12]
        normalized_route = route[:160]
        latency = max(0.0, float(duration_ms))
        status_class = f"{max(0, int(status_code)) // 100}xx"
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._request_count += 1
            self._status_classes[status_class] += 1
            self._latency_samples.append(latency)
            route_key = (normalized_method, normalized_route)
            if route_key not in self._routes and len(self._routes) >= MAX_ROUTE_SERIES:
                route_key = ("*", "/overflow")
            route_metrics = self._routes.setdefault(route_key, RouteMetrics())
            route_metrics.request_count += 1
            route_metrics.latency_samples.append(latency)
            if 400 <= status_code < 500:
                self._client_error_count += 1
                route_metrics.client_error_count += 1
            elif status_code >= 500:
                self._server_error_count += 1
                route_metrics.server_error_count += 1

    def snapshot(
        self,
        *,
        p95_latency_budget_ms: float = DEFAULT_P95_LATENCY_BUDGET_MS,
        server_error_rate_budget: float = DEFAULT_SERVER_ERROR_RATE_BUDGET,
    ) -> dict[str, Any]:
        with self._lock:
            request_count = self._request_count
            client_error_count = self._client_error_count
            server_error_count = self._server_error_count
            in_flight = self._in_flight
            status_classes = dict(sorted(self._status_classes.items()))
            latency_values = list(self._latency_samples)
            route_values = [
                (
                    method,
                    route,
                    metrics.request_count,
                    metrics.client_error_count,
                    metrics.server_error_count,
                    list(metrics.latency_samples),
                )
                for (method, route), metrics in self._routes.items()
            ]

        latency = _latency_summary(latency_values)
        server_error_rate = (
            server_error_count / request_count if request_count else 0.0
        )
        p95_pass = request_count == 0 or latency["p95_ms"] <= p95_latency_budget_ms
        error_pass = server_error_rate <= server_error_rate_budget
        top_routes = []
        for method, route, count, client_errors, server_errors, samples in sorted(
            route_values, key=lambda item: (-item[2], item[0], item[1])
        )[:12]:
            top_routes.append(
                {
                    "method": method,
                    "route": route,
                    "request_count": count,
                    "client_error_count": client_errors,
                    "server_error_count": server_errors,
                    "server_error_rate": round(server_errors / count, 6) if count else 0.0,
                    "latency_ms": _latency_summary(samples),
                }
            )

        return {
            "status": (
                "warming_up"
                if request_count == 0
                else "ready"
                if p95_pass and error_pass
                else "attention"
            ),
            "generated_at": utc_now_iso(),
            "process_started_at": self._started_at,
            "uptime_seconds": round(time.monotonic() - self._started_monotonic, 3),
            "request_count": request_count,
            "in_flight_requests": in_flight,
            "client_error_count": client_error_count,
            "server_error_count": server_error_count,
            "server_error_rate": round(server_error_rate, 6),
            "status_classes": status_classes,
            "latency_ms": latency,
            "top_routes": top_routes,
            "budgets": {
                "p95_latency_ms": p95_latency_budget_ms,
                "server_error_rate": server_error_rate_budget,
            },
            "budget_checks": [
                {
                    "key": "p95_latency_budget",
                    "status": "pass" if p95_pass else "fail",
                    "observed": float(latency["p95_ms"]),
                    "threshold": p95_latency_budget_ms,
                    "unit": "ms",
                },
                {
                    "key": "server_error_rate_budget",
                    "status": "pass" if error_pass else "fail",
                    "observed": round(server_error_rate, 6),
                    "threshold": server_error_rate_budget,
                    "unit": "ratio",
                },
            ],
            "sample_capacity": MAX_GLOBAL_SAMPLES,
            "production_ready": False,
            "limitation": (
                "Process-local bounded telemetry and disposable CI load evidence do not "
                "establish production capacity, distributed tracing, retained metrics, "
                "alert delivery, or a measured production SLO."
            ),
        }


runtime_metrics = RuntimeMetrics()
