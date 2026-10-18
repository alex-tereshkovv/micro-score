# Observability and Performance Gate v1

MicroScore now has a bounded runtime-observability layer and a reproducible HTTP
performance smoke test. The goal is to catch regressions in the complete
request path before release, while keeping the evidence honest: this gate is
not a production capacity study or a measured service-level objective.

## Runtime Signals

Every FastAPI response exposes:

- `X-Request-ID`, preserving a valid caller-supplied correlation ID or creating
  a safe one;
- `Server-Timing: app;dur=...`, reporting application processing time;
- one structured completion event with method, route template, status, and
  duration.

The structured event deliberately excludes query strings, request/response
bodies, authorization headers, tokens, email addresses, and database URLs.
Route templates such as `/applications/{application_id}` are used instead of
record identifiers. Requests without a framework route template collapse to
`/unmatched`, so an unknown path cannot expose a value or create unbounded
metric cardinality.

`GET /admin/operations/runtime-readiness` provides an admin-only snapshot with:

- request, in-flight, 4xx, and 5xx counts;
- bounded p50, p95, p99, average, minimum, and maximum latency samples;
- the 12 busiest method/route-template pairs;
- explicit p95-latency and server-error-rate checks;
- a machine-readable `production_ready: false` boundary.

Memory is bounded to the latest 4,096 global latency samples, 512 samples per
route, and 128 route series plus one overflow bucket. Metrics are process-local
and reset when the API restarts.

## Regression Budgets

The default runtime snapshot uses:

| Check | Default budget | Meaning |
| --- | ---: | --- |
| Application p95 latency | `750 ms` | Recent process-local requests should remain below the release regression threshold. |
| Server error rate | `1%` | HTTP 5xx responses, not expected 4xx validation/auth responses, drive this check. |

The values can be overridden with
`MICROSCORE_OBSERVABILITY_P95_BUDGET_MS` and
`MICROSCORE_OBSERVABILITY_SERVER_ERROR_RATE_BUDGET`.

These are release budgets, not production SLOs. They have not been calibrated
against real traffic, a managed network, or a multi-instance deployment.

## HTTP Performance Smoke

Run the complete local gate:

```powershell
.venv\Scripts\python scripts\http-performance-smoke.py \
  --requests 160 \
  --concurrency 8 \
  --p95-budget-ms 750 \
  --min-throughput-rps 15
```

The script starts a real Uvicorn process, seeds synthetic applications, logs in
through the public API, warms the analyst queue, and distributes 160 requests
across `/health`, `/organizations`, and `/mfi/applications` with concurrency 8.
It fails if any response is unsuccessful, correlation headers are lost,
`Server-Timing` is missing, client p95 exceeds 750 ms, throughput falls below
15 requests/second, or the server snapshot records a 5xx response.

Local execution uses a disposable SQLite database. The independent
`observability-performance` CI job applies the PostgreSQL schema and runs the
same workload against disposable PostgreSQL 16. Keeping the job separate makes
a performance regression visible instead of hiding it inside the general test
suite.

The dry-run contract is inspectable without starting a server:

```powershell
.venv\Scripts\python scripts\http-performance-smoke.py --dry-run
```

## Interpreting Results

A passing run proves that this bounded synthetic workload completed inside its
generous regression budgets on that runner. It does not prove:

- production throughput, tail latency, concurrency limits, or availability;
- retained metrics, alert delivery, cross-instance aggregation, or tracing;
- database connection-pool behavior under sustained or burst traffic;
- capacity for real borrower or MFI workloads.

Before a real pilot, replace process-local telemetry with an authenticated
export path (for example OpenTelemetry plus retained metrics), define SLOs from
observed traffic, add alert ownership, and run sustained/soak tests in the
managed deployment environment with privacy-safe synthetic data.

## Evidence Map

| Evidence | Location |
| --- | --- |
| Runtime instrumentation | `src/microscore_api/observability.py`, `src/microscore_api/main.py` |
| Typed readiness contract | `src/microscore_api/schemas.py` |
| Unit/API/privacy checks | `tests/test_observability.py` |
| Executable workload | `scripts/http-performance-smoke.py` |
| PostgreSQL CI gate | `.github/workflows/ci.yml` |
| Release-gate traceability | `docs/ENGINEERING_QUALITY.md` |
