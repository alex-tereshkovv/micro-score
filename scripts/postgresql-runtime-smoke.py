"""Exercise the real repository contract against disposable PostgreSQL."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from microscore_api.database import create_repository  # noqa: E402
from microscore_api.seed import (  # noqa: E402
    DEMO_ORGANIZATION_ID,
    seed_demo_data,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    require(
        os.environ.get("MICROSCORE_STORAGE_BACKEND", "").lower() == "postgresql",
        "MICROSCORE_STORAGE_BACKEND=postgresql is required",
    )
    repository = create_repository()
    require(repository.storage_backend == "postgresql", "PostgreSQL runtime was not selected")

    seed = seed_demo_data(repository)
    require(seed["demo_portfolio_size"] >= 5, "Demo portfolio was not seeded")
    require(repository.get_active_model_version() is not None, "Active model is missing")

    suffix = uuid4().hex[:12]
    session_token = f"runtime-session-{suffix}"
    repository.create_session(session_token, "analyst@test.com")
    session_user = repository.get_user_by_token(session_token)
    require(session_user is not None, "Session round trip failed")
    require(session_user["organization_id"] == DEMO_ORGANIZATION_ID, "Session tenant mismatch")

    tenant_applications = repository.list_applications(DEMO_ORGANIZATION_ID)
    require(len(tenant_applications) >= 5, "Tenant-scoped queue is incomplete")
    scored = next(
        (
            item
            for item in tenant_applications
            if item["status"] in {"scored", "under_review"}
            and item.get("score_result")
        ),
        None,
    )
    require(scored is not None, "No mutable scored application exists")
    if scored["status"] == "scored":
        repository.record_application_decision(
            application_id=scored["id"],
            actor_email="analyst@test.com",
            decision="review",
            policy_name="balanced_review",
            note="Disposable PostgreSQL runtime parity check.",
        )

    invite_token = f"runtime-invite-{suffix}"
    repository.create_staff_invite(
        token=invite_token,
        email=f"runtime-{suffix}@example.test",
        role="mfi_analyst",
        organization_id=DEMO_ORGANIZATION_ID,
        created_by="admin@test.com",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    attempt_id = f"runtime-attempt-{suffix}"
    repository.record_staff_invite_delivery_attempt(
        attempt_id=attempt_id,
        token=invite_token,
        attempted_by="admin@test.com",
        provider="local_outbox",
        status="queued",
        channel="email",
        recipient=f"runtime-{suffix}@example.test",
        url_base="https://example.test/invites",
        note="Disposable runtime parity.",
    )
    require(
        repository.get_staff_invite_delivery_attempt(attempt_id) is not None,
        "Invite delivery JSON/worker round trip failed",
    )

    simulation_id = f"runtime-simulation-{suffix}"
    repository.create_portfolio_simulation(
        simulation_id=simulation_id,
        organization_id=DEMO_ORGANIZATION_ID,
        actor_email="analyst@test.com",
        portfolio_fingerprint="a" * 64,
        request_payload={"policy": "balanced_review", "iterations": 10, "seed": 42},
        result_payload={"scenarios": [{"scenario": "baseline"}]},
        created_at="2099-01-01T00:00:00+00:00",
    )
    require(
        repository.get_portfolio_simulation(simulation_id) is not None,
        "Portfolio simulation JSONB round trip failed",
    )
    require(repository.segment_analytics(DEMO_ORGANIZATION_ID), "Segment analytics are empty")
    require(repository.decision_analytics(DEMO_ORGANIZATION_ID)["application_count"] >= 5, "Decision analytics failed")
    require(repository.revoke_session(session_token), "Session revoke failed")

    readiness = repository.postgresql_migration_readiness()
    require(readiness["repository_backend_status"] == "implemented", "Runtime status mismatch")
    require(readiness["live_connection_tested"], "Live connection evidence missing")
    require(readiness["present_table_count"] == readiness["required_table_count"], "Schema parity failed")

    print(
        json.dumps(
            {
                "backend": repository.storage_backend,
                "runtime_version": "postgresql-runtime-v1",
                "repository_methods": readiness["repository_adapter_implemented_method_count"],
                "required_tables": readiness["required_table_count"],
                "tenant_applications": len(tenant_applications),
                "jsonb_round_trips": 2,
                "session_round_trip": True,
                "tenant_scope_verified": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
