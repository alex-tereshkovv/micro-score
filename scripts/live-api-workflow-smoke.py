from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
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


class SmokeFailure(AssertionError):
    pass


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


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
        expected_status: int = 200,
    ) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
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


def login(client: ApiClient, email: str, password: str, mfa_code: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"email": email, "password": password}
    if mfa_code:
        payload["mfa_code"] = mfa_code
    return client.request("POST", "/auth/login", payload=payload)


def assert_borrower_safe_application(application: dict[str, Any], *, expected_status: str) -> None:
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
        "decision_support",
        "review_packet",
        "action_plan",
        "policy_name",
        "note",
    }
    leaked = sorted(forbidden_fields.intersection(application))
    assert_true(not leaked, f"Borrower application leaked internal fields: {leaked}")
    assert_true(application["status"] == expected_status, f"Expected borrower status {expected_status}")
    assert_true(isinstance(application.get("status_message"), str), "Missing borrower status message")


def assert_borrower_safe_timeline(events: list[dict[str, Any]]) -> None:
    assert_true(events, "Borrower timeline should not be empty")
    forbidden_detail_keys = {
        "risk_band",
        "model_version",
        "policy_name",
        "decision",
        "note",
        "actor_email",
        "analyst_email",
        "checklist",
        "lifecycle",
        "action_plan",
        "review_packet",
    }
    for event in events:
        assert_true(event.get("actor_email") is None, "Borrower timeline leaked actor email")
        details = event.get("details") or {}
        leaked = sorted(forbidden_detail_keys.intersection(details))
        assert_true(not leaked, f"Borrower timeline leaked internal details: {leaked}")
        assert_true(set(details).issubset({"status"}), f"Unexpected borrower timeline details: {details}")


def run_workflow(client: ApiClient) -> dict[str, Any]:
    unique = uuid4().hex[:10]
    borrower_email = f"live-smoke-{unique}@example.com"
    borrower_password = "StrongPass1!"

    registered = client.request(
        "POST",
        "/auth/register",
        payload={"email": borrower_email, "password": borrower_password, "role": "borrower"},
    )
    borrower_token = registered["access_token"]
    assert_true(registered["role"] == "borrower", "Public registration should create a borrower")

    analyst_auth = login(client, "analyst@test.com", DEMO_PASSWORD, DEMO_MFA_CODE)
    analyst_token = analyst_auth["access_token"]
    assert_true(analyst_auth["role"] == "mfi_analyst", "Expected MFI analyst login")
    assert_true(
        analyst_auth["organization_id"] == DEMO_ORGANIZATION_ID,
        "Analyst should be scoped to the demo organization",
    )

    application = client.request(
        "POST",
        "/applications",
        token=borrower_token,
        payload={
            "requested_amount": 300000,
            "purpose": "inventory finance",
            "district": "Pavlodar city",
            "settlement_type": "urban",
            "organization_id": DEMO_ORGANIZATION_ID,
            "consent_confirmed": True,
            "consent_version": "synthetic-demo-v1",
            "behavioral_signals": {
                "annual_income": 4200000,
                "total_outstanding_debt": 650000,
                "mobile_banking_logins": 18,
                "online_transfer_frequency": 7,
                "atm_withdrawal_frequency": 2,
                "avg_deposit_amount": 140000,
                "debit_card_spending": 90000,
                "num_open_loans": 1,
                "late_payment_count": 0,
                "gender": "Female",
                "employment_status": "Self-employed",
            },
        },
    )
    application_id = application["id"]
    assert_borrower_safe_application(application, expected_status="submitted")
    assert_true(not application["terminal"], "Submitted borrower application should not be terminal")

    draft_packet = client.request(
        "GET",
        f"/mfi/applications/{application_id}/review-packet",
        token=analyst_token,
    )
    assert_true(draft_packet["lifecycle"]["status"] == "submitted", "Draft packet should be submitted")
    assert_true(draft_packet["lifecycle"]["scoring_action"] == "score", "Draft packet should require score")
    assert_true(draft_packet["lifecycle"]["allowed_decisions"] == [], "Draft packet should not allow decisions")
    assert_true("score_not_available" in draft_packet["governance_flags"], "Draft packet should flag missing score")

    scored = client.request(
        "POST",
        f"/mfi/applications/{application_id}/score",
        token=analyst_token,
    )
    assert_true(scored["status"] == "scored", "Scoring should move application to scored")
    assert_true(scored["organization_id"] == DEMO_ORGANIZATION_ID, "Scored row lost organization scope")
    assert_true(scored["score_result"]["risk_band"] in {"low", "medium", "high"}, "Missing risk band")

    scored_packet = client.request(
        "GET",
        f"/mfi/applications/{application_id}/review-packet",
        token=analyst_token,
    )
    assert_true(scored_packet["lifecycle"]["status"] == "scored", "Packet should be scored")
    assert_true(scored_packet["lifecycle"]["scoring_action"] == "rescore", "Packet should allow rescore")
    assert_true(
        scored_packet["lifecycle"]["allowed_decisions"] == ["review", "approve", "decline"],
        "Scored packet should expose review/approve/decline",
    )
    required_codes = {
        item["code"]
        for item in scored_packet["checklist"]
        if item["status"] == "required"
    }
    assert_true("verify_affordability" in required_codes, "Checklist should require affordability review")
    assert_true("record_human_decision" in required_codes, "Checklist should require human decision")

    reviewed = client.request(
        "POST",
        f"/mfi/applications/{application_id}/decision",
        token=analyst_token,
        payload={
            "decision": "review",
            "policy_name": "balanced_review",
            "note": "Live API smoke manual review.",
        },
    )
    assert_true(reviewed["status"] == "under_review", "Review decision should move to under_review")

    review_packet = client.request(
        "GET",
        f"/mfi/applications/{application_id}/review-packet",
        token=analyst_token,
    )
    assert_true(review_packet["lifecycle"]["allowed_decisions"] == ["approve", "decline"], "Review packet should allow final decisions only")
    assert_true(len(review_packet["decision_history"]) == 1, "Review packet should preserve manual review history")
    assert_true(
        review_packet["decision_history"][0]["note"] == "Live API smoke manual review.",
        "MFI packet should preserve analyst note internally",
    )

    approved = client.request(
        "POST",
        f"/mfi/applications/{application_id}/decision",
        token=analyst_token,
        payload={
            "decision": "approve",
            "policy_name": "balanced_review",
            "note": "Live API smoke evidence verified.",
        },
    )
    assert_true(approved["status"] == "approved", "Final decision should approve")

    terminal_packet = client.request(
        "GET",
        f"/mfi/applications/{application_id}/review-packet",
        token=analyst_token,
    )
    assert_true(terminal_packet["lifecycle"]["terminal"], "Terminal packet should be locked")
    assert_true(terminal_packet["lifecycle"]["scoring_action"] is None, "Terminal packet should disable scoring")
    assert_true(terminal_packet["lifecycle"]["allowed_decisions"] == [], "Terminal packet should disable decisions")
    assert_true(len(terminal_packet["decision_history"]) == 2, "Terminal packet should preserve decision history")

    client.request(
        "POST",
        f"/mfi/applications/{application_id}/score",
        token=analyst_token,
        expected_status=409,
    )
    client.request(
        "POST",
        f"/mfi/applications/{application_id}/decision",
        token=analyst_token,
        payload={
            "decision": "decline",
            "policy_name": "balanced_review",
            "note": "Attempted live smoke reversal.",
        },
        expected_status=409,
    )

    borrower_detail = client.request(
        "GET",
        f"/applications/{application_id}",
        token=borrower_token,
    )
    assert_borrower_safe_application(borrower_detail, expected_status="approved")
    assert_true(borrower_detail["terminal"], "Approved borrower detail should be terminal")

    borrower_history = client.request("GET", "/applications", token=borrower_token)
    assert_true(len(borrower_history) == 1, "New borrower should see exactly one owned application")
    assert_borrower_safe_application(borrower_history[0], expected_status="approved")

    borrower_timeline = client.request(
        "GET",
        f"/applications/{application_id}/timeline",
        token=borrower_token,
    )
    assert_borrower_safe_timeline(borrower_timeline)
    assert_true(
        [event["action"] for event in borrower_timeline] == [
            "application_created",
            "application_scored",
            "application_decision_recorded",
            "application_decision_recorded",
        ],
        "Borrower timeline should expose public lifecycle event order",
    )
    assert_true(
        borrower_timeline[-1]["title"] == "Application approved",
        "Borrower timeline should show approved final status",
    )

    return {
        "application_id": application_id,
        "borrower_email": borrower_email,
        "risk_band": scored["score_result"]["risk_band"],
        "borrower_timeline_events": len(borrower_timeline),
        "decision_history": len(terminal_packet["decision_history"]),
        "terminal": terminal_packet["lifecycle"]["terminal"],
    }


def main() -> None:
    started_at = time.time()
    with tempfile.TemporaryDirectory(prefix="microscore-live-smoke-") as tempdir:
        db_path = Path(tempdir) / "live-api-workflow.sqlite3"
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
        "mode": "live-api-workflow-smoke",
        "database": "temporary-sqlite",
        "seeded_applications": len(seed_result["demo_application_ids"]),
        "runtime_seconds": round(time.time() - started_at, 2),
        **workflow,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SmokeFailure as exc:
        print(f"live-api-workflow-smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
