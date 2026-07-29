from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

DEMO_PASSWORD = "password123"
DEMO_MFA_CODE = "246810"
DEMO_ORGANIZATION_ID = "pavlodar-demo-mfi"
DEMO_WEBHOOK_SECRET = "live-security-webhook-secret"


class SmokeFailure(AssertionError):
    pass


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def signed_webhook_headers(payload: dict[str, Any]) -> dict[str, str]:
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        DEMO_WEBHOOK_SECRET.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-MicroScore-Delivery-Timestamp": timestamp,
        "X-MicroScore-Delivery-Signature": f"sha256={signature}",
    }


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def decode_response(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> Any:
        data = None
        request_headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        if headers:
            request_headers.update(headers)

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = int(exc.code)

        decoded = decode_response(body)
        if status != expected_status:
            raise SmokeFailure(
                f"{method} {path} returned {status}, expected {expected_status}: {decoded}"
            )
        return decoded


def wait_for_api(client: ApiClient, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 30
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise SmokeFailure(f"uvicorn exited early with {process.returncode}:\n{output}")
        try:
            health = client.request("GET", "/health")
            assert_true(health.get("status") == "ok", "Health endpoint did not return ok")
            return
        except Exception as exc:  # noqa: BLE001 - retry startup failures.
            last_error = exc
            time.sleep(0.35)
    raise SmokeFailure(f"Timed out waiting for live API: {last_error}")


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=8)


def seed_database(db_path: Path) -> dict[str, Any]:
    os.environ["MICROSCORE_API_DB_PATH"] = str(db_path)
    from microscore_api.database import MicroScoreRepository
    from microscore_api.seed import seed_demo_data

    repository = MicroScoreRepository(db_path)
    return seed_demo_data(repository)


def start_api(db_path: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["MICROSCORE_API_DB_PATH"] = str(db_path)
    env["MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET"] = DEMO_WEBHOOK_SECRET
    env["PYTHONPATH"] = (
        str(SRC_ROOT)
        if not env.get("PYTHONPATH")
        else f"{SRC_ROOT}{os.pathsep}{env['PYTHONPATH']}"
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
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def login(
    client: ApiClient,
    email: str,
    password: str,
    *,
    mfa_code: str | None = None,
    expected_status: int = 200,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"email": email, "password": password}
    if mfa_code is not None:
        payload["mfa_code"] = mfa_code
    return client.request("POST", "/auth/login", payload=payload, expected_status=expected_status)


def check_security_ready(payload: dict[str, Any]) -> None:
    checks = {check["key"]: check for check in payload["checks"]}
    assert_true(payload["status"] == "ready", f"Expected ready security status: {payload}")
    assert_true(checks["mfa_attestation"]["status"] == "pass", "MFA attestation should pass")
    assert_true(checks["mfa_enforcement"]["status"] == "pass", "MFA enforcement should pass")
    assert_true(checks["invite_delivery"]["status"] == "pass", "Invite delivery should pass")
    assert_true(
        "not a completed production security review" in payload["limitation"],
        "Security readiness must keep prototype limitation visible",
    )


def assert_safe_staff_sessions(sessions: list[dict[str, Any]]) -> None:
    assert_true(sessions, "Expected at least one staff session")
    for session in sessions:
        assert_true("token" not in session, "Staff session list leaked raw token")
        assert_true("access_token" not in session, "Staff session list leaked access token")
        assert_true(session.get("session_id"), "Staff session should expose safe session id")
        assert_true(session.get("session_preview"), "Staff session should expose safe preview")


def assert_borrower_surface_is_separate(application: dict[str, Any]) -> None:
    forbidden_fields = {
        "borrower_email",
        "behavioral_signals",
        "score_result",
        "decision_result",
        "model_summary",
        "analyst_decision",
        "decision_history",
        "lifecycle",
        "checklist",
        "governance_flags",
        "session_id",
        "session_preview",
        "mfa_attested_at",
        "token_id",
        "token_preview",
    }
    leaked = sorted(forbidden_fields.intersection(application))
    assert_true(not leaked, f"Borrower surface leaked staff/internal fields: {leaked}")


def run_workflow(client: ApiClient) -> dict[str, Any]:
    unique = uuid4().hex[:10]
    invite_email = f"live-security-{unique}@example.com"
    invite_password = "StrongPass1!"
    borrower_email = f"borrower-security-{unique}@example.com"

    admin_auth = login(client, "admin@test.com", DEMO_PASSWORD, mfa_code=DEMO_MFA_CODE)
    admin_token = admin_auth["access_token"]
    assert_true(admin_auth["role"] == "admin", "Expected admin login")

    readiness = client.request("GET", "/admin/security/readiness", token=admin_token)
    check_security_ready(readiness)

    delivery_readiness = client.request(
        "GET",
        "/admin/staff-invites/delivery-readiness",
        token=admin_token,
    )
    assert_true(
        delivery_readiness["status"] == "blocked",
        "Local invite delivery provider should block production delivery readiness",
    )
    assert_true(
        delivery_readiness["configured_provider"] == "local_outbox",
        "Expected local_outbox as default invite delivery provider",
    )
    assert_true(
        any(
            row["key"] == "delivery_provider_not_production_ready"
            for row in delivery_readiness["production_blockers"]
        ),
        "Invite delivery readiness should expose provider production blocker",
    )
    transactional_profile = next(
        row
        for row in delivery_readiness["providers"]
        if row["provider"] == "transactional_email"
    )
    assert_true(
        transactional_profile["configuration_status"] == "missing",
        "Transactional email profile should report missing configuration by default",
    )
    assert_true(
        "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY"
        in transactional_profile["missing_environment"],
        "Transactional email profile should list missing API key environment name",
    )
    delivery_adapter_readiness = client.request(
        "GET",
        "/admin/staff-invites/delivery-adapter-readiness",
        token=admin_token,
    )
    adapter_blockers = {row["key"] for row in delivery_adapter_readiness["blockers"]}
    assert_true(
        delivery_adapter_readiness["status"] == "blocked"
        and delivery_adapter_readiness["provider"] == "transactional_email"
        and not delivery_adapter_readiness["send_adapter_ready"]
        and "external_send_adapter_disabled" in adapter_blockers
        and "invite_secret_material_not_available" in adapter_blockers
        and "adapter_idempotency_key" in delivery_adapter_readiness["safe_payload_fields"]
        and "raw_invite_token" in delivery_adapter_readiness["forbidden_payload_fields"],
        "Delivery adapter readiness should block external sends by design",
    )
    pre_pilot_readiness = client.request(
        "GET",
        "/admin/governance/pre-pilot-readiness",
        token=admin_token,
    )
    pre_pilot_checks = {
        check["key"]: check for check in pre_pilot_readiness.get("checks", [])
    }
    assert_true(
        pre_pilot_readiness["status"] == "blocked"
        and not pre_pilot_readiness["production_data_allowed"]
        and pre_pilot_readiness["readiness_score"] < 100
        and pre_pilot_checks["transactional_delivery_adapter"]["status"] == "blocker"
        and pre_pilot_checks["storage_backend"]["status"] == "blocker"
        and pre_pilot_checks["privacy_data_boundary"]["status"] == "pass"
        and "does not grant permission" in pre_pilot_readiness["limitation"],
        "Pre-pilot readiness should aggregate blocked real-data controls",
    )
    postgresql_readiness = client.request(
        "GET",
        "/admin/storage/postgresql-readiness",
        token=admin_token,
    )
    postgresql_parity = {
        check["key"]: check for check in postgresql_readiness.get("parity_checks", [])
    }
    postgresql_blockers = {
        blocker["key"] for blocker in postgresql_readiness.get("blockers", [])
    }
    assert_true(
        postgresql_readiness["status"] == "blocked"
        and postgresql_readiness["runtime_backend"] == "sqlite"
        and postgresql_readiness["target_backend"] == "postgresql"
        and postgresql_readiness["repository_backend_status"] == "not_implemented"
        and not postgresql_readiness["production_ready"]
        and "MICROSCORE_DATABASE_URL" in postgresql_readiness["missing_environment"]
        and postgresql_readiness["migration_artifact_count"] == 1
        and postgresql_readiness["latest_migration_version"] == "0001_initial_schema"
        and postgresql_readiness["versioned_migration_contract_present"]
        and postgresql_readiness["disposable_migration_ci_present"]
        and postgresql_readiness["repository_adapter_contract_status"] == "contract_only"
        and postgresql_readiness["repository_adapter_contract_method_count"] == 52
        and any(
            artifact["path"] == "migrations/postgresql/0001_initial_schema.sql"
            for artifact in postgresql_readiness.get("migration_artifacts", [])
        )
        and postgresql_parity["postgresql_schema_inventory"]["status"] == "pass"
        and postgresql_parity["postgresql_versioned_migration_artifacts"]["status"] == "pass"
        and postgresql_parity["postgresql_jsonb_mapping"]["status"] == "pass"
        and postgresql_parity["postgresql_disposable_migration_ci"]["status"] == "pass"
        and postgresql_parity["postgresql_repository_adapter_contract"]["status"] == "pass"
        and postgresql_parity["postgresql_repository_backend"]["status"] == "blocker",
        "PostgreSQL readiness should expose the migration draft and remaining blockers",
    )
    assert_true(
        "postgresql_versioned_migrations_missing" not in postgresql_blockers,
        "Versioned PostgreSQL migration blocker should be cleared by 0001 draft",
    )
    assert_true(
        "postgresql_disposable_migration_ci_missing" not in postgresql_blockers,
        "Disposable PostgreSQL migration CI blocker should be cleared by CI smoke job",
    )

    mfa_readiness = client.request("GET", "/admin/security/mfa-readiness", token=admin_token)
    assert_true(mfa_readiness["status"] == "ready", "Seeded staff MFA readiness should be ready")
    assert_true(mfa_readiness["missing_mfa_count"] == 0, "Seeded staff should have MFA attestation")

    missing_mfa = login(client, "analyst@test.com", DEMO_PASSWORD, expected_status=401)
    assert_true("MFA code required" in missing_mfa["detail"], "Staff login should require MFA code")
    invalid_mfa = login(
        client,
        "analyst@test.com",
        DEMO_PASSWORD,
        mfa_code="000000",
        expected_status=401,
    )
    assert_true("Invalid MFA code" in invalid_mfa["detail"], "Staff login should reject invalid MFA")

    readiness_after_failures = client.request("GET", "/admin/security/readiness", token=admin_token)
    failure_check = next(
        check for check in readiness_after_failures["checks"]
        if check["key"] == "mfa_challenge_failures"
    )
    assert_true(
        failure_check["status"] == "warning",
        "Failed live MFA challenges should surface as security readiness warning",
    )

    invite = client.request(
        "POST",
        "/admin/staff-invites",
        token=admin_token,
        payload={
            "email": invite_email,
            "role": "mfi_analyst",
            "organization_id": DEMO_ORGANIZATION_ID,
            "expires_in_hours": 24,
            "queue_delivery": True,
            "delivery_channel": "email",
            "delivery_recipient": invite_email,
            "delivery_provider": "local_outbox",
        },
        expected_status=201,
    )
    assert_true(invite["email"] == invite_email, "Invite email mismatch")
    assert_true(invite["organization_id"] == DEMO_ORGANIZATION_ID, "Invite organization mismatch")
    assert_true(invite.get("token"), "Invite creation should return one-time raw token")
    assert_true(invite.get("token_preview"), "Invite creation should return safe token preview")
    assert_true(invite.get("delivery_attempt", {}).get("status") == "sent", "Invite should record local delivery")

    listed_invites = client.request("GET", "/admin/staff-invites", token=admin_token)
    listed = next(row for row in listed_invites if row["token_id"] == invite["token_id"])
    assert_true("token" not in listed, "Invite list leaked raw token")
    assert_true("invite_url" not in listed, "Invite list leaked one-time URL")
    assert_true(listed["token_preview"] == invite["token_preview"], "Invite list should expose preview only")

    invite_health = client.request("GET", "/admin/staff-invites/health", token=admin_token)
    assert_true(invite_health["active_pending_count"] >= 1, "Invite health should include pending invite")
    delivered_readiness = client.request(
        "GET",
        "/admin/staff-invites/delivery-readiness",
        token=admin_token,
    )
    assert_true(
        delivered_readiness["active_pending_invite_count"] >= 1,
        "Invite delivery readiness should include active pending invite count",
    )
    assert_true(
        delivered_readiness["undelivered_active_invite_count"] == 0,
        "Queued local_outbox invite should already have audited delivery metadata",
    )

    webhook_invite = client.request(
        "POST",
        "/admin/staff-invites",
        token=admin_token,
        payload={
            "email": f"live-webhook-{unique}@example.com",
            "role": "mfi_analyst",
            "organization_id": DEMO_ORGANIZATION_ID,
            "expires_in_hours": 72,
            "queue_delivery": True,
            "delivery_channel": "email",
            "delivery_provider": "transactional_email",
        },
        expected_status=201,
    )
    assert_true(
        webhook_invite["delivery_attempt"]["status"] == "queued",
        "Transactional email attempt should wait for provider webhook",
    )
    webhook_payload = {
        "provider": "transactional_email",
        "provider_event_id": f"live-email-delivered-{unique}",
        "attempt_id": webhook_invite["delivery_attempt"]["attempt_id"],
        "event_type": "delivered",
        "recipient": webhook_invite["email"],
        "metadata": {"message_id": f"live-message-{unique}"},
    }
    webhook_event = client.request(
        "POST",
        "/webhooks/staff-invite-delivery",
        payload=webhook_payload,
        headers=signed_webhook_headers(webhook_payload),
        expected_status=202,
    )
    assert_true(
        webhook_event["mapped_attempt_status"] == "sent"
        and webhook_event["delivery_recorded"]
        and not webhook_event["was_duplicate"],
        "Signed delivery webhook should mark queued transactional attempt sent",
    )
    webhook_events = client.request(
        "GET",
        f"/admin/staff-invites/{urllib.parse.quote(webhook_invite['token_id'], safe='')}/delivery-events",
        token=admin_token,
    )
    assert_true(
        len(webhook_events) == 1
        and webhook_events[0]["provider_event_id"] == webhook_payload["provider_event_id"],
        "Webhook events should be visible to admins without raw tokens",
    )
    listed_after_webhook = client.request("GET", "/admin/staff-invites", token=admin_token)
    webhook_listed = next(
        row for row in listed_after_webhook if row["token_id"] == webhook_invite["token_id"]
    )
    assert_true(
        webhook_listed["delivered_at"]
        and webhook_listed["delivery_event_count"] == 1
        and webhook_listed["last_delivery_event_type"] == "delivered"
        and webhook_listed["last_delivery_status"] == "sent",
        "Webhook delivery should update invite delivery telemetry",
    )

    worker_invite = client.request(
        "POST",
        "/admin/staff-invites",
        token=admin_token,
        payload={
            "email": f"live-worker-{unique}@example.com",
            "role": "mfi_analyst",
            "organization_id": DEMO_ORGANIZATION_ID,
            "expires_in_hours": 72,
            "queue_delivery": True,
            "delivery_channel": "email",
            "delivery_provider": "local_queue",
        },
        expected_status=201,
    )
    assert_true(
        worker_invite["delivery_attempt"]["status"] == "queued"
        and worker_invite["delivery_attempt"]["worker_status"] == "queued"
        and worker_invite["delivery_attempt"]["next_worker_run_at"],
        "Local queue attempt should enter invite delivery worker outbox",
    )
    delivery_outbox = client.request(
        "GET",
        "/admin/staff-invites/delivery-outbox",
        token=admin_token,
    )
    worker_outbox_item = next(
        row
        for row in delivery_outbox["items"]
        if row["attempt_id"] == worker_invite["delivery_attempt"]["attempt_id"]
    )
    assert_true(
        delivery_outbox["status"] == "attention"
        and delivery_outbox["queued_count"] >= 1
        and delivery_outbox["due_count"] >= 1
        and worker_outbox_item["due"]
        and worker_outbox_item["adapter_idempotency_key"],
        "Invite delivery outbox should surface due queued worker attempts",
    )
    delivery_worker_run = client.request(
        "POST",
        "/admin/staff-invites/delivery-outbox/run",
        token=admin_token,
        payload={"limit": 10, "max_attempts": 1, "backoff_seconds": 60},
    )
    assert_true(
        delivery_worker_run["processed_count"] >= 1
        and delivery_worker_run["dead_lettered_count"] >= 1
        and any(
            row["attempt_id"] == worker_invite["delivery_attempt"]["attempt_id"]
            and row["action"] == "dead_lettered"
            and row["worker_status"] == "dead_letter"
            and row["adapter_idempotency_key"] == worker_outbox_item["adapter_idempotency_key"]
            for row in delivery_worker_run["results"]
        ),
        "Invite delivery worker should dead-letter exhausted local queue attempts",
    )
    worker_attempts = client.request(
        "GET",
        f"/admin/staff-invites/{urllib.parse.quote(worker_invite['token_id'], safe='')}/delivery-attempts",
        token=admin_token,
    )
    assert_true(
        len(worker_attempts) == 1
        and worker_attempts[0]["status"] == "failed"
        and worker_attempts[0]["worker_status"] == "dead_letter"
        and worker_attempts[0]["worker_attempt_count"] == 1,
        "Worker delivery attempts should expose dead-letter telemetry",
    )
    client.request(
        "DELETE",
        f"/admin/staff-invites/{urllib.parse.quote(worker_invite['token_id'], safe='')}",
        token=admin_token,
    )

    accepted = client.request(
        "POST",
        "/auth/accept-staff-invite",
        payload={"token": invite["token"], "password": invite_password, "mfa_code": DEMO_MFA_CODE},
    )
    analyst_token = accepted["access_token"]
    assert_true(accepted["role"] == "mfi_analyst", "Accepted invite should create analyst session")
    assert_true(accepted["organization_id"] == DEMO_ORGANIZATION_ID, "Accepted analyst should keep org scope")

    reused = client.request(
        "POST",
        "/auth/accept-staff-invite",
        payload={"token": invite["token"], "password": invite_password, "mfa_code": DEMO_MFA_CODE},
        expected_status=409,
    )
    assert_true(
        "accepted" in str(reused.get("detail", "")).lower(),
        "Accepted invite token should be one-time",
    )

    accepted_mfa = client.request("GET", "/admin/security/mfa-readiness", token=admin_token)
    accepted_row = next(row for row in accepted_mfa["accounts"] if row["email"] == invite_email)
    assert_true(accepted_row["status"] == "ready", "Accepted analyst should be MFA ready")
    assert_true(accepted_row["mfa_attested"], "Invite acceptance should record MFA attestation")

    sessions = client.request("GET", "/admin/staff-sessions", token=admin_token)
    assert_safe_staff_sessions(sessions)
    admin_session = next(row for row in sessions if row["email"] == "admin@test.com" and row["is_current_session"])
    new_analyst_session = next(row for row in sessions if row["email"] == invite_email)

    self_revoke = client.request(
        "DELETE",
        f"/admin/staff-sessions/{urllib.parse.quote(admin_session['session_id'], safe='')}",
        token=admin_token,
        expected_status=409,
    )
    assert_true("Current admin session" in self_revoke["detail"], "Current admin session should be protected")

    revoked = client.request(
        "DELETE",
        f"/admin/staff-sessions/{urllib.parse.quote(new_analyst_session['session_id'], safe='')}",
        token=admin_token,
    )
    assert_true(revoked["revoked"], "Target staff session should be revoked")
    assert_true(revoked["email"] == invite_email, "Revoked session email mismatch")

    client.request("GET", "/mfi/applications", token=analyst_token, expected_status=401)

    relogin = login(client, invite_email, invite_password, mfa_code=DEMO_MFA_CODE)
    relogin_token = relogin["access_token"]
    assert_true(relogin["role"] == "mfi_analyst", "Revoked analyst should be able to re-login")

    disabled = client.request(
        "POST",
        f"/admin/users/{urllib.parse.quote(invite_email, safe='')}/disable",
        token=admin_token,
    )
    assert_true(disabled["disabled_at"], "Disable should set disabled_at")
    assert_true(disabled["revoked_session_count"] >= 1, "Disable should revoke active analyst sessions")
    client.request("GET", "/mfi/applications", token=relogin_token, expected_status=401)
    disabled_login = login(
        client,
        invite_email,
        invite_password,
        mfa_code=DEMO_MFA_CODE,
        expected_status=403,
    )
    assert_true("Account disabled" in disabled_login["detail"], "Disabled staff login should fail")

    reactivated = client.request(
        "POST",
        f"/admin/users/{urllib.parse.quote(invite_email, safe='')}/reactivate",
        token=admin_token,
    )
    assert_true(not reactivated["disabled_at"], "Reactivation should clear disabled_at")
    reactivated_auth = login(client, invite_email, invite_password, mfa_code=DEMO_MFA_CODE)
    assert_true(reactivated_auth["role"] == "mfi_analyst", "Reactivated staff login should succeed")

    borrower_registered = client.request(
        "POST",
        "/auth/register",
        payload={"email": borrower_email, "password": "StrongPass1!", "role": "borrower"},
    )
    borrower_token = borrower_registered["access_token"]
    borrower_application = client.request(
        "POST",
        "/applications",
        token=borrower_token,
        payload={
            "requested_amount": 250000,
            "purpose": "security separation check",
            "district": "Pavlodar city",
            "settlement_type": "urban",
            "organization_id": DEMO_ORGANIZATION_ID,
            "consent_confirmed": True,
            "consent_version": "synthetic-demo-v1",
            "behavioral_signals": {},
        },
    )
    assert_borrower_surface_is_separate(borrower_application)
    borrower_history = client.request("GET", "/applications", token=borrower_token)
    assert_true(len(borrower_history) == 1, "Borrower should only see own application")
    assert_borrower_surface_is_separate(borrower_history[0])

    final_readiness = client.request("GET", "/admin/security/readiness", token=admin_token)
    final_checks = {check["key"]: check["status"] for check in final_readiness["checks"]}
    assert_true(final_checks["mfa_attestation"] == "pass", "Final MFA attestation should pass")
    assert_true(final_checks["mfa_enforcement"] == "pass", "Final MFA enforcement should pass")

    audit = client.request("GET", "/admin/audit-events", token=admin_token)
    actions = {event["action"] for event in audit}
    for expected_action in {
        "staff_invite_created",
        "staff_invite_delivery_attempted",
        "staff_invite_delivery_webhook_received",
        "staff_invite_delivery_worker_run",
        "staff_invite_accepted",
        "staff_session_revoked",
        "staff_user_disabled",
        "staff_user_reactivated",
        "staff_mfa_challenge_failed",
    }:
        assert_true(expected_action in actions, f"Missing audit action {expected_action}")
    worker_audit_events = [
        event for event in audit if event["action"] == "staff_invite_delivery_worker_run"
    ]
    assert_true(
        any(event["details"].get("adapter_idempotency_keys") for event in worker_audit_events),
        "Delivery worker audit should include adapter idempotency keys",
    )

    return {
        "invite_token_id": invite["token_id"],
        "invite_preview": invite["token_preview"],
        "staff_email": invite_email,
        "staff_sessions_seen": len(sessions),
        "revoked_session_email": revoked["email"],
        "borrower_application_id": borrower_application["id"],
        "mfa_failure_warning": failure_check["status"],
        "delivery_readiness_status": delivery_readiness["status"],
        "delivery_provider": delivery_readiness["configured_provider"],
        "delivery_adapter_status": delivery_adapter_readiness["status"],
        "pre_pilot_readiness": pre_pilot_readiness["status"],
        "pre_pilot_production_data_allowed": pre_pilot_readiness[
            "production_data_allowed"
        ],
        "postgresql_readiness": postgresql_readiness["status"],
        "postgresql_schema_inventory": postgresql_readiness["present_table_count"],
        "postgresql_migration_artifacts": postgresql_readiness[
            "migration_artifact_count"
        ],
        "postgresql_latest_migration": postgresql_readiness[
            "latest_migration_version"
        ],
        "postgresql_disposable_migration_ci": postgresql_readiness[
            "disposable_migration_ci_present"
        ],
        "postgresql_repository_adapter_contract": postgresql_readiness[
            "repository_adapter_contract_status"
        ],
        "postgresql_repository_adapter_methods": postgresql_readiness[
            "repository_adapter_contract_method_count"
        ],
        "transactional_email_contract_config": transactional_profile["configuration_status"],
        "delivery_webhook_events": len(webhook_events),
        "delivery_worker_dead_lettered": delivery_worker_run["dead_lettered_count"],
        "final_security_status": final_readiness["status"],
        "audit_actions_checked": 9,
    }


def main() -> None:
    started_at = time.time()
    with tempfile.TemporaryDirectory(prefix="microscore-live-security-") as tempdir:
        db_path = Path(tempdir) / "live-security-workflow.sqlite3"
        seed_result = seed_database(db_path)
        port = free_port()
        client = ApiClient(f"http://127.0.0.1:{port}")
        process = start_api(db_path, port)
        try:
            wait_for_api(client, process)
            workflow = run_workflow(client)
        finally:
            terminate_process(process)

    print(json.dumps({
        "mode": "live-security-workflow-smoke",
        "database": "temporary-sqlite",
        "seeded_applications": len(seed_result["demo_application_ids"]),
        "runtime_seconds": round(time.time() - started_at, 2),
        **workflow,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SmokeFailure as exc:
        print(f"live-security-workflow-smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
