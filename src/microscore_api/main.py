r"""FastAPI prototype for MicroScore.

Install app dependencies with:

    .venv\Scripts\python -m pip install -e ".[app]"

Run locally with:

    .venv\Scripts\python -m uvicorn microscore_api.main:app --reload
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
from io import StringIO
import os
from typing import Any
from urllib.parse import quote, urlparse
from uuid import uuid4

try:
    from fastapi import Depends, FastAPI, HTTPException, Request, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional extra
    raise ModuleNotFoundError(
        'MicroScore API dependencies are missing. Install them with: pip install -e ".[app]"'
    ) from exc

from .database import (
    DuplicateModelVersionError,
    DuplicateOrganizationError,
    DuplicateUserError,
    InvalidApplicationTransitionError,
    MicroScoreRepository,
    configured_session_ttl_hours,
)
from .analytics import policy_analytics as build_policy_analytics
from .privacy import find_forbidden_signal_paths
from .rate_limit import LoginRateLimiter
from .schemas import (
    ApplicationDecisionCreate,
    ApplicationCreate,
    ApplicationReviewPacketResponse,
    ApplicationTimelineEventResponse,
    AuditEventResponse,
    AuthResponse,
    BorrowerApplicationResponse,
    ClearApplicationsResponse,
    DecisionAnalyticsResponse,
    HealthResponse,
    IdentityReadinessResponse,
    LoanApplicationResponse,
    LoginRequest,
    LogoutResponse,
    MeResponse,
    MfaAttestationCreate,
    MfaAttestationResponse,
    MfaReadinessResponse,
    ModelStatusResponse,
    ModelVersionCreate,
    ModelVersionPublic,
    OrganizationCreate,
    OrganizationPublic,
    PilotReadinessResponse,
    PolicyAnalyticsResponse,
    PrePilotReadinessResponse,
    PostgresMigrationReadinessResponse,
    PortfolioSimulationRequest,
    PortfolioSimulationResponse,
    PortfolioSimulationSummary,
    RegisterRequest,
    SegmentAnalyticsRow,
    SecurityReadinessResponse,
    StaffInviteAccept,
    StaffInviteCreate,
    StaffInviteCreatedResponse,
    StaffInviteDeliveryAdapterReadinessResponse,
    StaffInviteDeliveryAttemptResponse,
    StaffInviteDeliveryCreate,
    StaffInviteDeliveryOutboxResponse,
    StaffInviteDeliveryOutboxRunCreate,
    StaffInviteDeliveryOutboxRunResponse,
    StaffInviteDeliveryReadinessResponse,
    StaffInviteDeliveryRetryCreate,
    StaffInviteDeliveryResponse,
    StaffInviteDeliveryWebhookCreate,
    StaffInviteDeliveryWebhookEventResponse,
    StaffInviteHealthResponse,
    StaffInviteRotateCreate,
    StaffInviteResponse,
    StaffSessionResponse,
    StaffSessionRevokeResponse,
    StaffUserCreate,
    StaffUserDisableResponse,
    StaffUserReactivateResponse,
    UserPublic,
)
from .scoring import get_scoring_service
from .security import create_token, hash_password, password_policy_violations, verify_password
from .simulation import simulate_portfolio


DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "https://alex-tereshkovv.github.io",
)
MFA_REQUIRED_ROLES = {"admin", "mfi_analyst"}
DEFAULT_PROTOTYPE_MFA_CODE = "246810"
DEFAULT_INVITE_WEB_BASE_URL = "http://127.0.0.1:5173"
DEFAULT_INVITE_DELIVERY_PROVIDER = "local_outbox"
MFA_CHALLENGE_FAILURE_WINDOW_HOURS = 24
TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT = (
    "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY",
    "MICROSCORE_TRANSACTIONAL_EMAIL_FROM",
    "MICROSCORE_TRANSACTIONAL_EMAIL_TEMPLATE_ID",
    "MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET",
)
TRANSACTIONAL_EMAIL_OPTIONAL_ENVIRONMENT = (
    "MICROSCORE_TRANSACTIONAL_EMAIL_API_BASE_URL",
    "MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION",
    "MICROSCORE_TRANSACTIONAL_EMAIL_SEND_ENABLED",
)
INVITE_DELIVERY_WEBHOOK_SIGNATURE_HEADER = "x-microscore-delivery-signature"
INVITE_DELIVERY_WEBHOOK_TIMESTAMP_HEADER = "x-microscore-delivery-timestamp"
INVITE_DELIVERY_WEBHOOK_REPLAY_WINDOW_SECONDS = 300
INVITE_DELIVERY_WEBHOOK_EVENT_STATUS_MAP = {
    "delivered": "sent",
    "bounced": "failed",
    "failed": "failed",
    "deferred": "queued",
}
INVITE_DELIVERY_WORKER_LIMITATION = (
    "Invite Delivery Worker v1 is an audited local outbox runner. It can classify queued "
    "attempts, schedule retries, and dead-letter exhausted items, but it does not send "
    "messages through an external provider in this prototype."
)
INVITE_DELIVERY_ADAPTER_LIMITATION = (
    "Transactional Delivery Adapter Boundary v1 defines safe configuration, "
    "idempotency, payload, and webhook-correlation contracts, but external sending "
    "is disabled in this prototype. Queued worker attempts persist only token ids, "
    "not raw invite secrets, so a future production sender must use a dedicated "
    "one-time link issuance service or send while the raw token is still in process."
)
INVITE_DELIVERY_ADAPTER_SAFE_PAYLOAD_FIELDS = (
    "provider",
    "attempt_id",
    "adapter_idempotency_key",
    "recipient",
    "channel",
    "template_id_env_name",
    "sender_env_name",
    "invite_token_preview",
    "organization_id",
)
INVITE_DELIVERY_ADAPTER_FORBIDDEN_PAYLOAD_FIELDS = (
    "raw_invite_token",
    "full_invite_url",
    "api_key",
    "webhook_secret",
    "authorization",
    "password",
)
INVITE_DELIVERY_ADAPTER_WEBHOOK_CORRELATION_FIELDS = (
    "provider",
    "provider_event_id",
    "attempt_id",
    "adapter_idempotency_key",
)
INVITE_DELIVERY_PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "local_outbox": {
        "attempt_status": "sent",
        "mode": "local_audit_outbox",
        "production_ready": False,
        "sends_message": False,
        "audit_only": True,
        "requires_external_secret": False,
        "summary": (
            "Records a local audited outbox receipt and marks delivery sent "
            "inside the prototype."
        ),
        "action": "Replace with a transactional email or secure-message provider before pilot onboarding.",
        "error": None,
    },
    "manual_receipt": {
        "attempt_status": "sent",
        "mode": "manual_receipt",
        "production_ready": False,
        "sends_message": False,
        "audit_only": True,
        "requires_external_secret": False,
        "summary": "Records that an operator manually copied or sent the invite link.",
        "action": "Use only for demos; require transactional delivery before real staff onboarding.",
        "error": None,
    },
    "local_queue": {
        "attempt_status": "queued",
        "mode": "local_queue",
        "production_ready": False,
        "sends_message": False,
        "audit_only": True,
        "requires_external_secret": False,
        "summary": "Queues a local delivery attempt without marking the invite delivered.",
        "action": "Retry through a working provider, rotate stale links, or revoke the invite.",
        "error": None,
    },
    "local_fail": {
        "attempt_status": "failed",
        "mode": "local_failure_simulator",
        "production_ready": False,
        "sends_message": False,
        "audit_only": True,
        "requires_external_secret": False,
        "summary": "Simulates a failed local delivery provider for release-gate coverage.",
        "action": "Retry with a working provider and keep the failure visible in audit events.",
        "error": "Local delivery provider simulated failure.",
    },
    "transactional_email": {
        "attempt_status": "queued",
        "mode": "transactional_email_contract",
        "production_ready": False,
        "sends_message": False,
        "audit_only": False,
        "requires_external_secret": True,
        "summary": (
            "Validates the future transactional email adapter configuration "
            "and records safe audited delivery attempts."
        ),
        "action": (
            "Set API key, sender, template, webhook secret, secret rotation, "
            "bounce handling, and delivery webhooks before enabling production sends."
        ),
        "error": "Transactional email provider is not integrated in this prototype.",
    },
}
LOCAL_INVITE_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
MFA_READINESS_LIMITATION = (
    "MFA Readiness v2 records staff attestation and the local prototype requires "
    "a second-factor code for staff sessions; it is not a production identity provider."
)


def configured_cors_origins() -> list[str]:
    raw_value = os.environ.get("MICROSCORE_CORS_ORIGINS", "").strip()
    if not raw_value:
        return list(DEFAULT_CORS_ORIGINS)
    origins = [item.strip().rstrip("/") for item in raw_value.split(",")]
    return [origin for origin in origins if origin]


def configured_prototype_mfa_code() -> str:
    return os.environ.get("MICROSCORE_PROTOTYPE_MFA_CODE", DEFAULT_PROTOTYPE_MFA_CODE).strip()


def configured_invite_web_base_url() -> str:
    return os.environ.get("MICROSCORE_INVITE_WEB_BASE_URL", DEFAULT_INVITE_WEB_BASE_URL).strip()


def configured_invite_delivery_provider() -> str:
    return os.environ.get(
        "MICROSCORE_INVITE_DELIVERY_PROVIDER",
        DEFAULT_INVITE_DELIVERY_PROVIDER,
    ).strip() or DEFAULT_INVITE_DELIVERY_PROVIDER


def configured_transactional_email_webhook_secret() -> str:
    return os.environ.get("MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET", "").strip()


def configured_transactional_email_secret_version() -> str:
    return os.environ.get("MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION", "").strip()


def configured_transactional_email_send_enabled() -> bool:
    return os.environ.get(
        "MICROSCORE_TRANSACTIONAL_EMAIL_SEND_ENABLED",
        "",
    ).strip().lower() in {"1", "true", "yes", "on"}


def _configured_environment_names(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if os.environ.get(name, "").strip()]


def _missing_environment_names(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not os.environ.get(name, "").strip()]


def _looks_like_email_address(value: str) -> bool:
    normalized = value.strip()
    if "@" not in normalized:
        return False
    local_part, domain = normalized.rsplit("@", 1)
    return bool(local_part and "." in domain and not domain.startswith("."))


def _transactional_email_configuration_profile() -> dict[str, Any]:
    required_environment = list(TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT)
    optional_environment = list(TRANSACTIONAL_EMAIL_OPTIONAL_ENVIRONMENT)
    configured_environment = _configured_environment_names(
        TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT + TRANSACTIONAL_EMAIL_OPTIONAL_ENVIRONMENT
    )
    missing_environment = _missing_environment_names(TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT)
    warnings: list[str] = []

    sender = os.environ.get("MICROSCORE_TRANSACTIONAL_EMAIL_FROM", "").strip()
    if sender and not _looks_like_email_address(sender):
        warnings.append("MICROSCORE_TRANSACTIONAL_EMAIL_FROM must look like a sender email address.")

    api_base_url = os.environ.get("MICROSCORE_TRANSACTIONAL_EMAIL_API_BASE_URL", "").strip()
    if api_base_url:
        parsed_api_base = urlparse(api_base_url)
        if parsed_api_base.scheme != "https" or not parsed_api_base.netloc:
            warnings.append("MICROSCORE_TRANSACTIONAL_EMAIL_API_BASE_URL must be a valid HTTPS URL.")

    if missing_environment:
        status_value = "missing"
    elif warnings:
        status_value = "invalid"
    else:
        status_value = "ready"

    return {
        "configuration_status": status_value,
        "configuration_ready": status_value == "ready",
        "required_environment": required_environment,
        "optional_environment": optional_environment,
        "configured_environment": configured_environment,
        "missing_environment": missing_environment,
        "configuration_warnings": warnings,
    }


def _provider_configuration_defaults() -> dict[str, Any]:
    return {
        "configuration_status": "not_required",
        "configuration_ready": True,
        "required_environment": [],
        "configured_environment": [],
        "missing_environment": [],
        "configuration_warnings": [],
    }


def _verify_staff_invite_delivery_webhook_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
) -> None:
    secret = configured_transactional_email_webhook_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invite delivery webhook secret is not configured",
        )
    if not signature_header or not timestamp_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invite delivery webhook signature required",
        )
    try:
        timestamp_value = int(timestamp_header)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid invite delivery webhook timestamp",
        ) from exc

    now_timestamp = int(datetime.now(timezone.utc).timestamp())
    if abs(now_timestamp - timestamp_value) > INVITE_DELIVERY_WEBHOOK_REPLAY_WINDOW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invite delivery webhook timestamp outside replay window",
        )

    supplied_signature = signature_header.strip()
    if supplied_signature.startswith("sha256="):
        supplied_signature = supplied_signature.removeprefix("sha256=")
    signed_payload = str(timestamp_value).encode("utf-8") + b"." + raw_body
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid invite delivery webhook signature",
        )


def _invite_delivery_provider_profile(provider: str | None) -> dict[str, Any]:
    provider_name = (provider or configured_invite_delivery_provider()).strip()
    provider_name = provider_name or DEFAULT_INVITE_DELIVERY_PROVIDER
    profile = INVITE_DELIVERY_PROVIDER_PROFILES.get(provider_name)
    if profile is None:
        return {
            "provider": provider_name,
            "attempt_status": "queued",
            "mode": "unknown_contract",
            "production_ready": False,
            "configuration_status": "missing",
            "configuration_ready": False,
            "sends_message": False,
            "audit_only": True,
            "requires_https_invite_url": True,
            "requires_external_secret": True,
            "required_environment": [],
            "configured_environment": [],
            "missing_environment": [],
            "configuration_warnings": [
                f"Provider {provider_name!r} is not registered in the invite delivery contract."
            ],
            "summary": "Delivery provider has no local sender implementation yet.",
            "action": (
                "Register the provider contract, secret handling, webhook/audit "
                "mapping, and failure semantics before use."
            ),
            "error": "Delivery provider has no local sender implementation yet.",
        }
    configuration = _provider_configuration_defaults()
    provider_error = profile["error"]
    if provider_name == "transactional_email":
        configuration = _transactional_email_configuration_profile()
        if configuration["missing_environment"]:
            provider_error = "Transactional email provider is missing required configuration."
        elif configuration["configuration_warnings"]:
            provider_error = "Transactional email provider configuration is invalid."
        else:
            provider_error = (
                "Transactional email configuration is present, but external "
                "sends are disabled in this prototype adapter."
            )
    return {
        "provider": provider_name,
        "attempt_status": profile["attempt_status"],
        "mode": profile["mode"],
        "production_ready": profile["production_ready"],
        "configuration_status": configuration["configuration_status"],
        "configuration_ready": configuration["configuration_ready"],
        "sends_message": profile["sends_message"],
        "audit_only": profile["audit_only"],
        "requires_https_invite_url": True,
        "requires_external_secret": profile["requires_external_secret"],
        "required_environment": configuration["required_environment"],
        "configured_environment": configuration["configured_environment"],
        "missing_environment": configuration["missing_environment"],
        "configuration_warnings": configuration["configuration_warnings"],
        "summary": profile["summary"],
        "action": profile["action"],
        "error": provider_error,
    }


def _invite_delivery_provider_result(provider: str | None) -> tuple[str, str, str | None]:
    profile = _invite_delivery_provider_profile(provider)
    return profile["provider"], profile["attempt_status"], profile["error"]


def _staff_invite_delivery_adapter_readiness_response() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    provider = "transactional_email"
    profile = _invite_delivery_provider_profile(provider)
    configuration = _transactional_email_configuration_profile()
    secret_version = configured_transactional_email_secret_version()
    external_send_enabled = configured_transactional_email_send_enabled()
    secret_rotation_ready = bool(secret_version) and configuration["configuration_ready"]
    blockers: list[dict[str, Any]] = [
        {
            "key": "external_send_adapter_disabled",
            "severity": "blocker",
            "summary": (
                "Transactional email external sends are disabled in the prototype adapter."
            ),
            "action": (
                "Implement a signed provider adapter with timeout, retry, idempotency, "
                "secret isolation, and delivery webhook reconciliation before enabling sends."
            ),
        },
        {
            "key": "invite_secret_material_not_available",
            "severity": "blocker",
            "summary": (
                "Queued worker attempts persist invite token ids and previews only, "
                "not raw invite tokens or full invite URLs."
            ),
            "action": (
                "Add a production one-time link issuance service or send while the "
                "raw invite token is still in process; do not persist raw invite secrets."
            ),
        },
    ]
    warnings: list[dict[str, Any]] = []
    if configuration["missing_environment"]:
        blockers.append(
            {
                "key": "transactional_email_configuration_missing",
                "severity": "blocker",
                "summary": (
                    "Transactional email adapter is missing required environment "
                    f"variable(s): {len(configuration['missing_environment'])}."
                ),
                "action": (
                    "Set API key, sender, template id, and webhook secret using "
                    "secret storage; never return secret values through API responses."
                ),
            }
        )
    if configuration["configuration_warnings"]:
        blockers.append(
            {
                "key": "transactional_email_configuration_invalid",
                "severity": "blocker",
                "summary": "Transactional email adapter configuration contains invalid values.",
                "action": "Fix sender/API base URL configuration before adapter testing.",
            }
        )
    if not secret_version:
        blockers.append(
            {
                "key": "secret_rotation_version_missing",
                "severity": "blocker",
                "summary": (
                    "Transactional email secret version is not declared for rotation evidence."
                ),
                "action": (
                    "Set MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION to a non-secret "
                    "rotation label before production adapter tests."
                ),
            }
        )
    if external_send_enabled:
        warnings.append(
            {
                "key": "external_send_flag_ignored",
                "severity": "warning",
                "summary": (
                    "MICROSCORE_TRANSACTIONAL_EMAIL_SEND_ENABLED is set, but this "
                    "prototype still refuses external delivery sends."
                ),
                "action": (
                    "Keep the flag off until the real adapter implementation and "
                    "production controls are reviewed."
                ),
            }
        )

    return {
        "status": "blocked" if blockers else "ready",
        "generated_at": generated_at,
        "provider": provider,
        "adapter_mode": "prototype_boundary_no_external_send",
        "send_adapter_ready": False if blockers else profile["production_ready"],
        "external_send_enabled": external_send_enabled,
        "configuration_status": configuration["configuration_status"],
        "configuration_ready": configuration["configuration_ready"],
        "secret_rotation_ready": secret_rotation_ready,
        "idempotency_key_strategy": "sha256(provider:attempt_id:invite_token_id)",
        "safe_payload_fields": list(INVITE_DELIVERY_ADAPTER_SAFE_PAYLOAD_FIELDS),
        "forbidden_payload_fields": list(INVITE_DELIVERY_ADAPTER_FORBIDDEN_PAYLOAD_FIELDS),
        "webhook_correlation_fields": list(
            INVITE_DELIVERY_ADAPTER_WEBHOOK_CORRELATION_FIELDS
        ),
        "required_environment": configuration["required_environment"],
        "optional_environment": configuration["optional_environment"],
        "configured_environment": configuration["configured_environment"],
        "missing_environment": configuration["missing_environment"],
        "blockers": blockers,
        "warnings": warnings,
        "next_required_controls": blockers + warnings,
        "limitation": INVITE_DELIVERY_ADAPTER_LIMITATION,
    }


app = FastAPI(
    title="MicroScore API",
    version="0.1.0",
    description="Prototype API for borrower applications, MFI review, and behavioral risk scoring.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
security = HTTPBearer()


@lru_cache(maxsize=1)
def get_repository() -> MicroScoreRepository:
    return MicroScoreRepository()


@lru_cache(maxsize=1)
def get_login_rate_limiter() -> LoginRateLimiter:
    return LoginRateLimiter()


def _login_rate_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{email}"


def _raise_login_rate_limit(retry_after: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def _prototype_mfa_code_matches(mfa_code: str | None) -> bool:
    expected = configured_prototype_mfa_code()
    provided = (mfa_code or "").strip()
    return bool(expected and provided and hmac.compare_digest(provided, expected))


def _staff_mfa_failure_reason_from_exception(exc: HTTPException) -> str:
    detail = str(exc.detail)
    if "attestation required" in detail:
        return "missing_attestation"
    if "MFA code required" in detail:
        return "missing_code"
    if "Invalid MFA code" in detail:
        return "invalid_code"
    return "challenge_failed"


def _record_staff_mfa_challenge_failed(
    repository: MicroScoreRepository,
    *,
    actor_email: str,
    entity_type: str,
    entity_id: str,
    reason: str,
    source: str,
    mfa_code: str | None,
    method: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    event_details = {
        "reason": reason,
        "source": source,
        "method": method or "prototype_mfa_code",
        "prototype": True,
        "mfa_code_present": bool((mfa_code or "").strip()),
    }
    if details:
        event_details.update(details)
    repository.record_audit_event(
        actor_email=actor_email,
        action="staff_mfa_challenge_failed",
        entity_type=entity_type,
        entity_id=entity_id,
        details=event_details,
    )


def _verify_staff_mfa_for_session(user: dict[str, Any], mfa_code: str | None) -> bool:
    if user["role"] not in MFA_REQUIRED_ROLES:
        return False
    if user.get("mfa_attested_at") is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA attestation required before staff login",
        )
    if not (mfa_code or "").strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA code required",
        )
    if not _prototype_mfa_code_matches(mfa_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )
    return True


def _verify_invite_acceptance_mfa(role: str, mfa_code: str | None) -> None:
    if role not in MFA_REQUIRED_ROLES:
        return
    if not (mfa_code or "").strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA code required",
        )
    if not _prototype_mfa_code_matches(mfa_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )


def _validate_new_password(password: str) -> None:
    violations = password_policy_violations(password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Password does not meet the registration policy",
                "requirements": violations,
            },
        )


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _staff_invite_token_id(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _staff_invite_token_preview(token_id: str) -> str:
    return f"{token_id[:12]}..."


def _staff_invite_delivery_adapter_idempotency_key(attempt: dict[str, Any]) -> str:
    material = (
        f"{attempt.get('provider', '')}:"
        f"{attempt.get('attempt_id', '')}:"
        f"{attempt.get('invite_token', '')}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _invite_url_base_is_safe(url_base: str | None) -> bool:
    parsed = urlparse((url_base or "").strip())
    if parsed.scheme == "https" and parsed.netloc:
        return True
    if parsed.scheme == "http" and parsed.hostname in LOCAL_INVITE_HOSTS:
        return True
    return False


def _validated_invite_url_base() -> str:
    base = configured_invite_web_base_url().rstrip("/")
    if not _invite_url_base_is_safe(base):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "MICROSCORE_INVITE_WEB_BASE_URL must be HTTPS, or local HTTP for development."
            ),
        )
    return base


def _build_staff_invite_url(raw_token: str) -> str:
    return f"{_validated_invite_url_base()}/#/accept-staff-invite?token={quote(raw_token, safe='')}"


def _staff_invite_status_value(invite: dict[str, Any]) -> str:
    if invite.get("revoked_at"):
        return "revoked"
    if invite.get("accepted_at"):
        return "accepted"
    if _parse_utc_datetime(invite["expires_at"]) <= datetime.now(timezone.utc):
        return "expired"
    return "pending"


def _staff_invite_is_active_pending(
    invite: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(timezone.utc)
    return (
        not invite.get("accepted_at")
        and not invite.get("revoked_at")
        and _parse_utc_datetime(invite["expires_at"]) > now
    )


def _active_pending_staff_invite_for_email(
    repository: MicroScoreRepository,
    email: str,
    *,
    exclude_token_id: str | None = None,
) -> dict[str, Any] | None:
    normalized_email = email.strip().lower()
    for invite in repository.list_staff_invites():
        if invite["token"] == exclude_token_id:
            continue
        if invite["email"] != normalized_email:
            continue
        if _staff_invite_is_active_pending(invite):
            return invite
    return None


def _staff_invite_response(
    invite: dict[str, Any],
    *,
    raw_token: str | None = None,
    invite_url: str | None = None,
    delivery_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = {
        "token_id": invite["token"],
        "token_preview": _staff_invite_token_preview(invite["token"]),
        "email": invite["email"],
        "role": invite["role"],
        "organization_id": invite["organization_id"],
        "created_by": invite.get("created_by"),
        "created_at": invite["created_at"],
        "expires_at": invite["expires_at"],
        "accepted_at": invite.get("accepted_at"),
        "accepted_by": invite.get("accepted_by"),
        "revoked_at": invite.get("revoked_at"),
        "revoked_by": invite.get("revoked_by"),
        "delivered_at": invite.get("delivered_at"),
        "delivered_by": invite.get("delivered_by"),
        "delivery_channel": invite.get("delivery_channel"),
        "delivery_recipient": invite.get("delivery_recipient"),
        "delivery_url_base": invite.get("delivery_url_base"),
        "delivery_note": invite.get("delivery_note"),
        "delivery_attempt_count": invite.get("delivery_attempt_count", 0),
        "last_delivery_attempt_at": invite.get("last_delivery_attempt_at"),
        "last_delivery_status": invite.get("last_delivery_status"),
        "last_delivery_provider": invite.get("last_delivery_provider"),
        "delivery_event_count": invite.get("delivery_event_count", 0),
        "last_delivery_event_at": invite.get("last_delivery_event_at"),
        "last_delivery_event_type": invite.get("last_delivery_event_type"),
    }
    if raw_token is not None:
        response["token"] = raw_token
    if invite_url is not None:
        response["invite_url"] = invite_url
    if delivery_attempt is not None:
        response["delivery_attempt"] = _staff_invite_delivery_attempt_response(delivery_attempt)
    if "was_already_delivered" in invite:
        response["was_already_delivered"] = invite["was_already_delivered"]
    return response


def _staff_invite_delivery_attempt_response(
    attempt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "attempt_id": attempt["attempt_id"],
        "invite_token_id": attempt["invite_token"],
        "attempted_at": attempt["attempted_at"],
        "attempted_by": attempt.get("attempted_by"),
        "provider": attempt["provider"],
        "status": attempt["status"],
        "channel": attempt["channel"],
        "recipient": attempt.get("recipient"),
        "delivery_url_base": attempt.get("delivery_url_base"),
        "note": attempt.get("note"),
        "error": attempt.get("error"),
        "worker_status": attempt.get("worker_status", "completed"),
        "worker_attempt_count": attempt.get("worker_attempt_count", 0),
        "next_worker_run_at": attempt.get("next_worker_run_at"),
        "dead_letter_at": attempt.get("dead_letter_at"),
        "last_worker_error": attempt.get("last_worker_error"),
    }


def _staff_invite_delivery_webhook_event_response(
    event: dict[str, Any],
    *,
    delivery_recorded: bool | None = None,
) -> dict[str, Any]:
    event_type = event["event_type"]
    mapped_status = event.get(
        "mapped_attempt_status",
        INVITE_DELIVERY_WEBHOOK_EVENT_STATUS_MAP[event_type],
    )
    return {
        "event_id": event["event_id"],
        "provider_event_id": event["provider_event_id"],
        "attempt_id": event["attempt_id"],
        "invite_token_id": event["invite_token"],
        "provider": event["provider"],
        "event_type": event_type,
        "mapped_attempt_status": mapped_status,
        "received_at": event["received_at"],
        "occurred_at": event.get("occurred_at"),
        "recipient": event.get("recipient"),
        "error": event.get("error"),
        "was_duplicate": bool(event.get("was_duplicate", False)),
        "delivery_recorded": bool(
            delivery_recorded
            if delivery_recorded is not None
            else mapped_status == "sent"
        ),
    }


def _session_id_for_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _staff_session_response(
    session: dict[str, Any],
    *,
    current_session_id: str | None = None,
) -> dict[str, Any]:
    session_id = session["session_id"]
    return {
        "session_id": session_id,
        "session_preview": f"{session_id[:12]}...",
        "email": session["email"],
        "role": session["role"],
        "organization_id": session.get("organization_id"),
        "session_created_at": session["session_created_at"],
        "session_expires_at": session["session_expires_at"],
        "session_ttl_seconds": session["session_ttl_seconds"],
        "is_current_session": session_id == current_session_id,
    }


def _record_staff_invite_created(
    repository: MicroScoreRepository,
    *,
    actor_email: str,
    token_id: str,
    email: str,
    role: str,
    organization_id: str,
    expires_at: str,
    source: str = "admin_create",
) -> None:
    repository.record_audit_event(
        actor_email=actor_email,
        action="staff_invite_created",
        entity_type="staff_invite",
        entity_id=token_id,
        details={
            "email": email,
            "role": role,
            "organization_id": organization_id,
            "expires_at": expires_at,
            "token_preview": _staff_invite_token_preview(token_id),
            "source": source,
        },
    )


def _record_staff_invite_delivery_attempt(
    repository: MicroScoreRepository,
    *,
    invite: dict[str, Any],
    actor_email: str,
    channel: str,
    recipient: str | None,
    note: str | None,
    provider: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    token_id = invite["token"]
    delivery_url_base = _validated_invite_url_base()
    normalized_recipient = (recipient or invite["email"]).strip() or invite["email"]
    normalized_note = note.strip() if note else None
    provider_name, status_value, provider_error = _invite_delivery_provider_result(provider)
    attempt = repository.record_staff_invite_delivery_attempt(
        attempt_id=str(uuid4()),
        token=token_id,
        attempted_by=actor_email,
        provider=provider_name,
        status=status_value,
        channel=channel,
        recipient=normalized_recipient,
        url_base=delivery_url_base,
        note=normalized_note,
        error=provider_error,
    )
    repository.record_audit_event(
        actor_email=actor_email,
        action="staff_invite_delivery_attempted",
        entity_type="staff_invite_delivery_attempt",
        entity_id=attempt["attempt_id"],
        details={
            "staff_invite_token_preview": _staff_invite_token_preview(token_id),
            "staff_invite_token_id": token_id,
            "provider": provider_name,
            "status": attempt["status"],
            "delivery_channel": channel,
            "delivery_recipient": normalized_recipient,
            "delivery_url_base": delivery_url_base,
            "note_present": bool(normalized_note),
            "error_present": bool(provider_error),
        },
    )
    if status_value != "sent":
        refreshed = repository.get_staff_invite(token_id)
        if refreshed is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff invite not found",
            )
        refreshed["was_already_delivered"] = False
        return attempt, refreshed

    delivered = repository.mark_staff_invite_delivered(
        token_id,
        delivered_by=actor_email,
        channel=channel,
        recipient=normalized_recipient,
        url_base=delivery_url_base,
        note=normalized_note,
    )
    if delivered is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    if not delivered.get("was_already_delivered", False):
        repository.record_audit_event(
            actor_email=actor_email,
            action="staff_invite_delivered",
            entity_type="staff_invite",
            entity_id=token_id,
            details={
                "email": invite["email"],
                "role": invite["role"],
                "organization_id": invite["organization_id"],
                "token_preview": _staff_invite_token_preview(token_id),
                "delivery_attempt_id": attempt["attempt_id"],
                "delivery_provider": provider_name,
                "delivery_channel": channel,
                "delivery_recipient": normalized_recipient,
                "delivery_url_base": delivery_url_base,
                "note_present": bool(normalized_note),
            },
        )
    return attempt, delivered


def _record_staff_invite_delivery_webhook_event(
    repository: MicroScoreRepository,
    *,
    payload: StaffInviteDeliveryWebhookCreate,
) -> dict[str, Any]:
    provider = payload.provider.strip()
    provider_event_id = payload.provider_event_id.strip()
    attempt_id = payload.attempt_id.strip()
    mapped_status = INVITE_DELIVERY_WEBHOOK_EVENT_STATUS_MAP[payload.event_type]
    attempt = repository.get_staff_invite_delivery_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite delivery attempt not found",
        )
    if attempt["provider"] != provider:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Webhook provider does not match delivery attempt provider",
        )
    invite = repository.get_staff_invite(attempt["invite_token"])
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )

    event = repository.record_staff_invite_delivery_event(
        event_id=str(uuid4()),
        provider=provider,
        provider_event_id=provider_event_id,
        attempt_id=attempt_id,
        token=attempt["invite_token"],
        event_type=payload.event_type,
        mapped_attempt_status=mapped_status,
        occurred_at=payload.occurred_at,
        recipient=payload.recipient,
        error=payload.error,
        metadata=payload.metadata,
    )
    if event.get("was_duplicate"):
        return _staff_invite_delivery_webhook_event_response(
            event,
            delivery_recorded=False,
        )

    updated_attempt = repository.update_staff_invite_delivery_attempt_status(
        attempt_id,
        status=mapped_status,
        error=payload.error,
        worker_status="retry_scheduled" if mapped_status == "queued" else "completed",
        next_worker_run_at=(
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat()
        if mapped_status == "queued"
        else None,
        dead_letter_at=None,
        last_worker_error=payload.error if mapped_status == "queued" else None,
    )
    if updated_attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite delivery attempt not found",
        )

    delivery_recorded = False
    if mapped_status == "sent":
        delivered = repository.mark_staff_invite_delivered(
            attempt["invite_token"],
            delivered_by=None,
            channel=attempt["channel"],
            recipient=payload.recipient or attempt.get("recipient"),
            url_base=attempt.get("delivery_url_base") or _validated_invite_url_base(),
            note=attempt.get("note"),
        )
        if delivered is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff invite not found",
            )
        delivery_recorded = not delivered.get("was_already_delivered", False)
        if delivery_recorded:
            repository.record_audit_event(
                actor_email=None,
                action="staff_invite_delivered",
                entity_type="staff_invite",
                entity_id=attempt["invite_token"],
                details={
                    "email": invite["email"],
                    "role": invite["role"],
                    "organization_id": invite["organization_id"],
                    "token_preview": _staff_invite_token_preview(attempt["invite_token"]),
                    "delivery_attempt_id": attempt_id,
                    "delivery_provider": provider,
                    "delivery_channel": attempt["channel"],
                    "delivery_recipient": payload.recipient or attempt.get("recipient"),
                    "delivery_url_base": attempt.get("delivery_url_base"),
                    "source": "delivery_webhook",
                    "provider_event_id": provider_event_id,
                },
            )

    repository.record_audit_event(
        actor_email=None,
        action="staff_invite_delivery_webhook_received",
        entity_type="staff_invite_delivery_event",
        entity_id=event["event_id"],
        details={
            "staff_invite_token_preview": _staff_invite_token_preview(
                attempt["invite_token"],
            ),
            "staff_invite_token_id": attempt["invite_token"],
            "delivery_attempt_id": attempt_id,
            "provider": provider,
            "provider_event_id": provider_event_id,
            "event_type": payload.event_type,
            "mapped_attempt_status": mapped_status,
            "recipient": payload.recipient,
            "error_present": bool(payload.error),
            "metadata_keys": sorted(payload.metadata),
            "delivery_recorded": delivery_recorded,
        },
    )
    return _staff_invite_delivery_webhook_event_response(
        event,
        delivery_recorded=delivery_recorded,
    )


def _staff_invite_delivery_outbox_item(
    attempt: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    active_pending = (
        not attempt.get("accepted_at")
        and not attempt.get("revoked_at")
        and _parse_utc_datetime(attempt["expires_at"]) > now
    )
    worker_status = attempt.get("worker_status", "completed")
    next_worker_run_at = attempt.get("next_worker_run_at")
    due_at = _parse_utc_datetime(next_worker_run_at) if next_worker_run_at else None
    due = (
        attempt["status"] == "queued"
        and worker_status in {"queued", "retry_scheduled"}
        and not attempt.get("dead_letter_at")
        and (due_at is None or due_at <= now)
    )
    return {
        "attempt_id": attempt["attempt_id"],
        "invite_token_id": attempt["invite_token"],
        "token_preview": _staff_invite_token_preview(attempt["invite_token"]),
        "email": attempt["email"],
        "provider": attempt["provider"],
        "adapter_idempotency_key": _staff_invite_delivery_adapter_idempotency_key(attempt),
        "attempt_status": attempt["status"],
        "worker_status": worker_status,
        "worker_attempt_count": attempt.get("worker_attempt_count", 0),
        "next_worker_run_at": next_worker_run_at,
        "dead_letter_at": attempt.get("dead_letter_at"),
        "last_worker_error": attempt.get("last_worker_error"),
        "due": due,
        "invite_active_pending": active_pending,
        "last_delivery_event_type": attempt.get("last_delivery_event_type"),
    }


def _staff_invite_delivery_outbox_response(
    repository: MicroScoreRepository,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    items = [
        _staff_invite_delivery_outbox_item(attempt, now=now)
        for attempt in repository.list_staff_invite_delivery_outbox_attempts()
    ]
    queued_count = sum(
        1
        for item in items
        if item["attempt_status"] == "queued"
        and item["worker_status"] in {"queued", "retry_scheduled"}
    )
    due_count = sum(1 for item in items if item["due"])
    retry_scheduled_count = sum(
        1 for item in items if item["worker_status"] == "retry_scheduled"
    )
    dead_letter_count = sum(1 for item in items if item["worker_status"] == "dead_letter")
    completed_count = sum(1 for item in items if item["worker_status"] == "completed")
    if dead_letter_count:
        recommended_action = (
            "Review dead-lettered invite delivery attempts, rotate stale links, "
            "or configure a real transactional provider before onboarding."
        )
    elif due_count:
        recommended_action = (
            "Run the invite delivery outbox worker or connect an external delivery provider."
        )
    else:
        recommended_action = "No invite delivery worker action is due."
    return {
        "status": "attention" if due_count or dead_letter_count else "ok",
        "generated_at": now.isoformat(),
        "queued_count": queued_count,
        "due_count": due_count,
        "retry_scheduled_count": retry_scheduled_count,
        "dead_letter_count": dead_letter_count,
        "completed_count": completed_count,
        "items": items,
        "recommended_action": recommended_action,
        "limitation": INVITE_DELIVERY_WORKER_LIMITATION,
    }


def _staff_invite_delivery_worker_error(provider: str) -> str:
    return (
        "Invite delivery worker cannot send through provider "
        f"'{provider}' in this prototype."
    )


def _run_staff_invite_delivery_outbox(
    repository: MicroScoreRepository,
    *,
    payload: StaffInviteDeliveryOutboxRunCreate,
    actor_email: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    generated_at = now.isoformat()
    attempts = repository.list_staff_invite_delivery_outbox_attempts()
    due_attempts = [
        attempt
        for attempt in attempts
        if _staff_invite_delivery_outbox_item(attempt, now=now)["due"]
    ][: payload.limit]
    results: list[dict[str, Any]] = []
    retry_scheduled_count = 0
    dead_lettered_count = 0
    completed_count = 0
    skipped_count = 0

    for attempt in due_attempts:
        item = _staff_invite_delivery_outbox_item(attempt, now=now)
        previous_worker_status = item["worker_status"]
        worker_attempt_count = int(item["worker_attempt_count"])
        result: dict[str, Any] = {
            "attempt_id": attempt["attempt_id"],
            "invite_token_id": attempt["invite_token"],
            "provider": attempt["provider"],
            "adapter_idempotency_key": item["adapter_idempotency_key"],
            "action": "dry_run" if payload.dry_run else "skipped",
            "previous_worker_status": previous_worker_status,
            "worker_status": previous_worker_status,
            "worker_attempt_count": worker_attempt_count,
            "next_worker_run_at": item["next_worker_run_at"],
            "dead_letter_at": item["dead_letter_at"],
            "error": item["last_worker_error"],
        }
        if payload.dry_run:
            skipped_count += 1
            results.append(result)
            continue

        if not item["invite_active_pending"]:
            updated = repository.update_staff_invite_delivery_worker_state(
                attempt["attempt_id"],
                status=attempt["status"],
                error=attempt.get("error"),
                worker_status="completed",
                worker_attempt_count=worker_attempt_count,
                next_worker_run_at=None,
                dead_letter_at=None,
                last_worker_error=None,
            )
            if updated is None:
                skipped_count += 1
                results.append(result)
                continue
            result.update(
                {
                    "action": "completed",
                    "worker_status": "completed",
                    "next_worker_run_at": None,
                    "dead_letter_at": None,
                    "error": None,
                }
            )
            completed_count += 1
            results.append(result)
            continue

        worker_attempt_count += 1
        worker_error = _staff_invite_delivery_worker_error(attempt["provider"])
        if worker_attempt_count >= payload.max_attempts:
            updated = repository.update_staff_invite_delivery_worker_state(
                attempt["attempt_id"],
                status="failed",
                error=worker_error,
                worker_status="dead_letter",
                worker_attempt_count=worker_attempt_count,
                next_worker_run_at=None,
                dead_letter_at=generated_at,
                last_worker_error=worker_error,
            )
            if updated is None:
                skipped_count += 1
                results.append(result)
                continue
            result.update(
                {
                    "action": "dead_lettered",
                    "worker_status": "dead_letter",
                    "worker_attempt_count": worker_attempt_count,
                    "next_worker_run_at": None,
                    "dead_letter_at": generated_at,
                    "error": worker_error,
                }
            )
            dead_lettered_count += 1
        else:
            next_worker_run_at = (
                now
                + timedelta(
                    seconds=payload.backoff_seconds
                    * (2 ** max(0, worker_attempt_count - 1)),
                )
            ).isoformat()
            updated = repository.update_staff_invite_delivery_worker_state(
                attempt["attempt_id"],
                status="queued",
                error=worker_error,
                worker_status="retry_scheduled",
                worker_attempt_count=worker_attempt_count,
                next_worker_run_at=next_worker_run_at,
                dead_letter_at=None,
                last_worker_error=worker_error,
            )
            if updated is None:
                skipped_count += 1
                results.append(result)
                continue
            result.update(
                {
                    "action": "scheduled_retry",
                    "worker_status": "retry_scheduled",
                    "worker_attempt_count": worker_attempt_count,
                    "next_worker_run_at": next_worker_run_at,
                    "dead_letter_at": None,
                    "error": worker_error,
                }
            )
            retry_scheduled_count += 1
        results.append(result)

    if not payload.dry_run:
        repository.record_audit_event(
            actor_email=actor_email,
            action="staff_invite_delivery_worker_run",
            entity_type="staff_invite_delivery_outbox",
            entity_id=str(uuid4()),
            details={
                "processed_count": len(results),
                "retry_scheduled_count": retry_scheduled_count,
                "dead_lettered_count": dead_lettered_count,
                "completed_count": completed_count,
                "skipped_count": skipped_count,
                "limit": payload.limit,
                "max_attempts": payload.max_attempts,
                "backoff_seconds": payload.backoff_seconds,
                "dry_run": payload.dry_run,
                "attempt_previews": [
                    _staff_invite_token_preview(result["invite_token_id"])
                    for result in results
                ],
                "adapter_idempotency_keys": [
                    result["adapter_idempotency_key"] for result in results
                ],
            },
        )

    return {
        "generated_at": generated_at,
        "dry_run": payload.dry_run,
        "processed_count": len(results),
        "retry_scheduled_count": retry_scheduled_count,
        "dead_lettered_count": dead_lettered_count,
        "completed_count": completed_count,
        "skipped_count": skipped_count,
        "results": results,
        "limitation": INVITE_DELIVERY_WORKER_LIMITATION,
    }


def _staff_invite_health_response(
    invites: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    window_hours: int = 24,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    expiring_deadline = now + timedelta(hours=window_hours)
    health: dict[str, Any] = {
        "status": "ok",
        "total_count": len(invites),
        "active_pending_count": 0,
        "expiring_soon_count": 0,
        "expired_pending_count": 0,
        "accepted_count": 0,
        "revoked_count": 0,
        "action_required_count": 0,
        "window_hours": window_hours,
        "oldest_pending_created_at": None,
        "next_expiring_at": None,
        "recommended_action": "No pending staff invite rotation action required.",
    }

    oldest_pending: datetime | None = None
    next_expiring: datetime | None = None
    for invite in invites:
        if invite.get("accepted_at"):
            health["accepted_count"] += 1
            continue
        if invite.get("revoked_at"):
            health["revoked_count"] += 1
            continue

        created_at = _parse_utc_datetime(invite["created_at"])
        expires_at = _parse_utc_datetime(invite["expires_at"])
        if oldest_pending is None or created_at < oldest_pending:
            oldest_pending = created_at

        if expires_at <= now:
            health["expired_pending_count"] += 1
            continue

        health["active_pending_count"] += 1
        if next_expiring is None or expires_at < next_expiring:
            next_expiring = expires_at
        if expires_at <= expiring_deadline:
            health["expiring_soon_count"] += 1

    health["action_required_count"] = (
        health["expired_pending_count"] + health["expiring_soon_count"]
    )
    health["oldest_pending_created_at"] = oldest_pending.isoformat() if oldest_pending else None
    health["next_expiring_at"] = next_expiring.isoformat() if next_expiring else None
    if health["action_required_count"]:
        health["status"] = "attention"
        health["recommended_action"] = (
            "Review expired or soon-expiring staff invites; revoke stale links "
            "and create fresh invites only when onboarding is still needed."
        )
    return health


def _recent_staff_mfa_failure_events(
    events: list[dict[str, Any]],
    *,
    now: datetime,
    window_hours: int = MFA_CHALLENGE_FAILURE_WINDOW_HOURS,
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(hours=window_hours)
    recent: list[dict[str, Any]] = []
    for event in events:
        if event.get("action") != "staff_mfa_challenge_failed":
            continue
        try:
            created_at = _parse_utc_datetime(event["created_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if created_at >= cutoff:
            recent.append(event)
    return recent


def _mfa_readiness_response(users: list[dict[str, Any]]) -> dict[str, Any]:
    accounts = []
    active_staff_count = 0
    mfa_attested_count = 0
    disabled_staff_count = 0
    missing_mfa_count = 0

    for user in users:
        if user["role"] not in MFA_REQUIRED_ROLES:
            continue
        disabled = user.get("disabled_at") is not None
        mfa_attested = user.get("mfa_attested_at") is not None
        mfa_required = not disabled
        if disabled:
            disabled_staff_count += 1
            account_status = "disabled"
        else:
            active_staff_count += 1
            if mfa_attested:
                mfa_attested_count += 1
                account_status = "ready"
            else:
                missing_mfa_count += 1
                account_status = "missing"
        accounts.append(
            {
                "email": user["email"],
                "role": user["role"],
                "organization_id": user.get("organization_id"),
                "disabled": disabled,
                "mfa_required": mfa_required,
                "mfa_attested": mfa_attested,
                "mfa_attested_at": user.get("mfa_attested_at"),
                "mfa_method": user.get("mfa_method"),
                "status": account_status,
            }
        )

    status_value = "blocked" if missing_mfa_count else "ready"
    recommended_action = (
        "Record MFA attestation for active admin and MFI analyst accounts before pilot use."
        if missing_mfa_count
        else "All active staff accounts have MFA attestation recorded."
    )
    return {
        "status": status_value,
        "active_staff_count": active_staff_count,
        "mfa_attested_count": mfa_attested_count,
        "missing_mfa_count": missing_mfa_count,
        "disabled_staff_count": disabled_staff_count,
        "accounts": accounts,
        "recommended_action": recommended_action,
        "limitation": MFA_READINESS_LIMITATION,
    }


def _security_readiness_response(repository: MicroScoreRepository) -> dict[str, Any]:
    users = repository.list_users()
    invites = repository.list_staff_invites()
    mfa_readiness = _mfa_readiness_response(users)
    invite_health = _staff_invite_health_response(invites)
    session_ttl_hours = configured_session_ttl_hours()
    session_ttl_seconds = int(round(session_ttl_hours * 3600))
    checks: list[dict[str, Any]] = []

    if mfa_readiness["missing_mfa_count"]:
        checks.append(
            {
                "key": "mfa_attestation",
                "label": "Staff MFA attestation",
                "status": "blocker",
                "summary": (
                    f"{mfa_readiness['missing_mfa_count']} active staff account(s) "
                    "lack MFA attestation."
                ),
                "action": "Record MFA attestation for every active admin and MFI analyst account.",
            }
        )
    else:
        checks.append(
            {
                "key": "mfa_attestation",
                "label": "Staff MFA attestation",
                "status": "pass",
                "summary": "All active staff accounts have MFA attestation recorded.",
                "action": "Keep attestation current when staff accounts change.",
            }
        )

    if invite_health["action_required_count"]:
        checks.append(
            {
                "key": "invite_hygiene",
                "label": "Staff invite hygiene",
                "status": "blocker",
                "summary": (
                    f"{invite_health['action_required_count']} pending invite(s) "
                    "are expired or expiring soon."
                ),
                "action": "Revoke stale invites and create fresh links only when onboarding is active.",
            }
        )
    else:
        checks.append(
            {
                "key": "invite_hygiene",
                "label": "Staff invite hygiene",
                "status": "pass",
                "summary": "No expired or soon-expiring pending staff invites require action.",
                "action": "Continue reviewing invite health before pilot access.",
            }
        )

    ttl_status = "pass" if session_ttl_hours <= 8 else "warning"
    checks.append(
        {
            "key": "session_ttl",
            "label": "Session lifetime",
            "status": ttl_status,
            "summary": f"Current session TTL is {session_ttl_seconds} seconds.",
            "action": (
                "Keep reviewer sessions at or below 8 hours."
                if ttl_status == "pass"
                else "Reduce MICROSCORE_SESSION_TTL_HOURS to 8 hours or less before pilot use."
            ),
        }
    )

    checks.extend(
        [
            {
                "key": "mfa_enforcement",
                "label": "Login-time MFA enforcement",
                "status": "pass",
                "summary": "Staff login requires an MFA-attested account and a prototype second-factor code.",
                "action": "Replace the prototype shared-code control with TOTP/WebAuthn or an external identity provider before real user data.",
            },
        ]
    )

    now = datetime.now(timezone.utc)
    recent_mfa_failures = _recent_staff_mfa_failure_events(
        repository.list_audit_events(),
        now=now,
    )
    if recent_mfa_failures:
        affected_entities = {
            event.get("entity_id")
            for event in recent_mfa_failures
            if event.get("entity_id")
        }
        checks.append(
            {
                "key": "mfa_challenge_failures",
                "label": "Recent staff MFA challenge failures",
                "status": "warning",
                "summary": (
                    f"{len(recent_mfa_failures)} failed staff MFA challenge(s) "
                    f"across {len(affected_entities)} account/invite target(s) in the last "
                    f"{MFA_CHALLENGE_FAILURE_WINDOW_HOURS} hours."
                ),
                "action": "Review failed MFA audit events before pilot access and rotate credentials if needed.",
            }
        )
    else:
        checks.append(
            {
                "key": "mfa_challenge_failures",
                "label": "Recent staff MFA challenge failures",
                "status": "pass",
                "summary": (
                    f"No failed staff MFA challenges were recorded in the last "
                    f"{MFA_CHALLENGE_FAILURE_WINDOW_HOURS} hours."
                ),
                "action": "Continue monitoring MFA challenge failures in the audit log.",
            }
        )

    active_pending_invites = [
        invite for invite in invites if _staff_invite_is_active_pending(invite, now=now)
    ]
    undelivered_invites = [
        invite for invite in active_pending_invites if not invite.get("delivered_at")
    ]
    failed_delivery_invites = [
        invite
        for invite in active_pending_invites
        if not invite.get("delivered_at") and invite.get("last_delivery_status") == "failed"
    ]
    unsafe_delivered_invites = [
        invite
        for invite in active_pending_invites
        if invite.get("delivered_at")
        and not _invite_url_base_is_safe(invite.get("delivery_url_base"))
    ]
    if undelivered_invites:
        checks.append(
            {
                "key": "invite_delivery",
                "label": "Invite delivery and HTTPS links",
                "status": "blocker",
                "summary": (
                    f"{len(undelivered_invites)} active pending staff invite(s) "
                    "lack audited delivery metadata."
                ),
                "action": "Record invite delivery before sharing onboarding links.",
            }
        )
    elif unsafe_delivered_invites:
        checks.append(
            {
                "key": "invite_delivery",
                "label": "Invite delivery and HTTPS links",
                "status": "blocker",
                "summary": (
                    f"{len(unsafe_delivered_invites)} delivered staff invite(s) "
                    "use a non-HTTPS, non-local URL base."
                ),
                "action": "Use HTTPS invite URLs outside local development.",
            }
        )
    else:
        checks.append(
            {
                "key": "invite_delivery",
                "label": "Invite delivery and HTTPS links",
                "status": "pass",
                "summary": (
                    "All active pending staff invites have audited delivery metadata."
                    if active_pending_invites
                    else "No active pending staff invites require delivery."
                ),
                "action": (
                    "Use audited delivery records and move to transactional email before production onboarding."
                ),
            }
        )

    if failed_delivery_invites:
        checks.append(
            {
                "key": "invite_delivery_attempts",
                "label": "Invite delivery provider attempts",
                "status": "warning",
                "summary": (
                    f"{len(failed_delivery_invites)} active pending staff invite(s) "
                    "have a failed latest delivery attempt."
                ),
                "action": "Retry invite delivery with a working provider, or rotate/revoke stale links.",
            }
        )
    else:
        checks.append(
            {
                "key": "invite_delivery_attempts",
                "label": "Invite delivery provider attempts",
                "status": "pass",
                "summary": "No active pending staff invite has a failed latest delivery attempt.",
                "action": "Monitor delivery attempts and retry failures before sharing onboarding links.",
            }
        )

    blockers = [check for check in checks if check["status"] == "blocker"]
    warnings = [check for check in checks if check["status"] == "warning"]
    if blockers:
        status_value = "blocked"
    elif warnings:
        status_value = "review"
    else:
        status_value = "ready"
    return {
        "status": status_value,
        "generated_at": _utc_now_iso(),
        "blockers_count": len(blockers),
        "warnings_count": len(warnings),
        "checks": checks,
        "recommended_actions": [check["action"] for check in checks if check["status"] != "pass"],
        "limitation": (
            "Security Readiness v1 is a pre-pilot control summary for the local prototype; "
            "MFA enforcement uses a local prototype code and is not a completed production security review."
        ),
    }


def _staff_invite_delivery_readiness_response(
    repository: MicroScoreRepository,
) -> dict[str, Any]:
    invites = repository.list_staff_invites()
    configured_provider = configured_invite_delivery_provider()
    configured_profile = _invite_delivery_provider_profile(configured_provider)
    invite_url_base = configured_invite_web_base_url()
    parsed_base = urlparse(invite_url_base)
    invite_url_https = parsed_base.scheme == "https"
    invite_url_host = (parsed_base.hostname or "").lower()
    invite_url_local = invite_url_host in LOCAL_INVITE_HOSTS
    now = datetime.now(timezone.utc)
    active_pending_invites = [
        invite for invite in invites if _staff_invite_is_active_pending(invite, now=now)
    ]
    undelivered_active_invites = [
        invite for invite in active_pending_invites if not invite.get("delivered_at")
    ]
    failed_latest_attempts = [
        invite
        for invite in active_pending_invites
        if invite.get("last_delivery_status") == "failed"
    ]

    provider_names = list(INVITE_DELIVERY_PROVIDER_PROFILES)
    if configured_provider not in provider_names:
        provider_names.insert(0, configured_provider)
    providers = [
        {
            **_invite_delivery_provider_profile(provider),
            "configured": provider == configured_provider,
        }
        for provider in provider_names
    ]

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not configured_profile["production_ready"]:
        blockers.append(
            {
                "key": "delivery_provider_not_production_ready",
                "severity": "blocker",
                "summary": (
                    f"Configured provider {configured_provider!r} is "
                    f"{configured_profile['mode']} and is not production-ready."
                ),
                "action": configured_profile["action"],
            }
        )
    if configured_profile.get("missing_environment"):
        blockers.append(
            {
                "key": "delivery_provider_configuration_missing",
                "severity": "blocker",
                "summary": (
                    f"Configured provider {configured_provider!r} is missing "
                    f"{len(configured_profile['missing_environment'])} required "
                    "environment variable(s)."
                ),
                "action": (
                    "Set the required transactional email environment variables "
                    "without exposing secret values in logs or API responses."
                ),
            }
        )
    if configured_profile.get("configuration_warnings"):
        blockers.append(
            {
                "key": "delivery_provider_configuration_invalid",
                "severity": "blocker",
                "summary": (
                    f"Configured provider {configured_provider!r} has invalid "
                    "delivery configuration."
                ),
                "action": "Fix provider sender/API URL configuration before enabling delivery attempts.",
            }
        )
    if not invite_url_https:
        blockers.append(
            {
                "key": "invite_url_not_https",
                "severity": "blocker",
                "summary": f"Invite URL base {invite_url_base!r} is not HTTPS.",
                "action": "Use a verified HTTPS invite origin before real staff onboarding.",
            }
        )
    if invite_url_local:
        blockers.append(
            {
                "key": "invite_url_local_origin",
                "severity": "blocker",
                "summary": f"Invite URL base {invite_url_base!r} points to a local host.",
                "action": "Move invite links to the deployed HTTPS application origin.",
            }
        )
    if undelivered_active_invites:
        blockers.append(
            {
                "key": "undelivered_active_invites",
                "severity": "blocker",
                "summary": (
                    f"{len(undelivered_active_invites)} active pending staff "
                    "invite(s) do not have audited delivery metadata."
                ),
                "action": "Record delivery, retry through a working provider, rotate, or revoke each invite.",
            }
        )
    if failed_latest_attempts:
        warnings.append(
            {
                "key": "failed_latest_delivery_attempts",
                "severity": "warning",
                "summary": (
                    f"{len(failed_latest_attempts)} active pending staff invite(s) "
                    "have a failed latest delivery attempt."
                ),
                "action": "Retry through a working provider or rotate/revoke the invite.",
            }
        )

    status_value = "blocked" if blockers else "review" if warnings else "ready"
    return {
        "status": status_value,
        "generated_at": _utc_now_iso(),
        "configured_provider": configured_provider,
        "default_provider": DEFAULT_INVITE_DELIVERY_PROVIDER,
        "invite_url_base": invite_url_base,
        "invite_url_https": invite_url_https,
        "invite_url_local": invite_url_local,
        "active_pending_invite_count": len(active_pending_invites),
        "undelivered_active_invite_count": len(undelivered_active_invites),
        "failed_latest_attempt_count": len(failed_latest_attempts),
        "providers": providers,
        "production_blockers": blockers,
        "warnings": warnings,
        "next_required_controls": blockers + warnings,
        "limitation": (
            "Staff Invite Delivery Readiness v2 validates provider contract, "
            "HTTPS origin, secret/configuration presence, and audited delivery "
            "evidence. It does not expose secret values and the prototype "
            "transactional email adapter records attempts without sending "
            "external email."
        ),
    }


def _identity_readiness_response(repository: MicroScoreRepository) -> dict[str, Any]:
    users = repository.list_users()
    invites = repository.list_staff_invites()
    staff_sessions = repository.list_active_sessions(staff_only=True)
    mfa_readiness = _mfa_readiness_response(users)
    delivery_readiness = _staff_invite_delivery_readiness_response(repository)
    storage = repository.storage_readiness()
    session_ttl_hours = configured_session_ttl_hours()
    session_ttl_seconds = int(round(session_ttl_hours * 3600))
    provider = configured_invite_delivery_provider()
    invite_base_url = configured_invite_web_base_url()
    now = datetime.now(timezone.utc)
    active_pending_invites = [
        invite for invite in invites if _staff_invite_is_active_pending(invite, now=now)
    ]

    components: list[dict[str, Any]] = [
        {
            "key": "auth_provider",
            "label": "Authentication provider",
            "status": "blocker",
            "severity": "blocker",
            "summary": (
                "Staff authentication uses local email/password accounts managed "
                "inside the prototype API."
            ),
            "action": (
                "Replace local staff password auth with an external IdP before "
                "handling real borrower or MFI staff data."
            ),
        },
        {
            "key": "mfa_posture",
            "label": "Staff MFA posture",
            "status": "blocker" if mfa_readiness["missing_mfa_count"] else "warning",
            "severity": "blocker" if mfa_readiness["missing_mfa_count"] else "warning",
            "summary": (
                f"{mfa_readiness['missing_mfa_count']} active staff account(s) "
                "lack MFA attestation."
                if mfa_readiness["missing_mfa_count"]
                else (
                    "All active staff accounts have MFA attestation, but enforcement "
                    "still uses the local prototype code."
                )
            ),
            "action": (
                "Record missing staff MFA attestations."
                if mfa_readiness["missing_mfa_count"]
                else "Replace prototype-code MFA with IdP-backed TOTP/WebAuthn."
            ),
        },
        {
            "key": "invite_delivery",
            "label": "Invite delivery mode",
            "status": "blocker" if delivery_readiness["status"] == "blocked" else "warning",
            "severity": "blocker" if delivery_readiness["status"] == "blocked" else "warning",
            "summary": (
                f"Invite delivery provider is {provider!r} with URL base {invite_base_url!r}; "
                f"delivery readiness is {delivery_readiness['status']}."
            ),
            "action": (
                delivery_readiness["next_required_controls"][0]["action"]
                if delivery_readiness["next_required_controls"]
                else "Move staff invite delivery to transactional email or approved secure messaging."
            ),
        },
        {
            "key": "session_control",
            "label": "Staff session controls",
            "status": "pass" if session_ttl_hours <= 8 else "warning",
            "severity": "info" if session_ttl_hours <= 8 else "warning",
            "summary": (
                f"{len(staff_sessions)} active staff session(s); TTL is "
                f"{session_ttl_seconds} seconds."
            ),
            "action": (
                "Continue using hashed session ids/previews for inventory and targeted revoke."
                if session_ttl_hours <= 8
                else "Reduce MICROSCORE_SESSION_TTL_HOURS to 8 hours or less."
            ),
        },
        {
            "key": "rate_limit",
            "label": "Login rate limiting",
            "status": "blocker",
            "severity": "blocker",
            "summary": "Login throttling is in-memory and protects only one API process.",
            "action": "Move rate limiting to the external IdP, Redis, or managed edge control.",
        },
        {
            "key": "storage_backend",
            "label": "Identity storage backend",
            "status": "blocker" if not storage["production_ready"] else "pass",
            "severity": "blocker" if not storage["production_ready"] else "info",
            "summary": (
                f"Storage backend is {storage['backend']!r}; "
                f"production_ready={storage['production_ready']}."
            ),
            "action": (
                "Complete PostgreSQL migration readiness and disposable integration tests."
                if not storage["production_ready"]
                else "Keep storage health checks in the release gate."
            ),
        },
        {
            "key": "tenant_isolation",
            "label": "Tenant isolation",
            "status": "pass",
            "severity": "info",
            "summary": (
                "MFI queues, review packets, analytics, simulations, and staff "
                "invites are organization-scoped; admins retain global visibility."
            ),
            "action": "Keep organization_id checks on every new staff or MFI endpoint.",
        },
    ]

    blockers = [
        {
            "key": component["key"],
            "severity": "blocker",
            "summary": component["summary"],
            "action": component["action"],
        }
        for component in components
        if component["status"] == "blocker"
    ]
    warnings = [
        {
            "key": component["key"],
            "severity": "warning",
            "summary": component["summary"],
            "action": component["action"],
        }
        for component in components
        if component["status"] == "warning"
    ]
    next_required_controls = blockers + warnings
    status_value = "blocked" if blockers else "review" if warnings else "ready"

    return {
        "status": status_value,
        "generated_at": _utc_now_iso(),
        "auth_provider_mode": "local_password_prototype",
        "invite_delivery_mode": provider,
        "mfa_mode": "prototype_shared_code_with_admin_attestation",
        "session_control_mode": "local_bearer_sessions_with_admin_revoke",
        "rate_limit_mode": "in_memory_single_process",
        "storage_backend": storage["backend"],
        "tenant_isolation_mode": "organization_id_scoped_mfi_access",
        "active_staff_count": mfa_readiness["active_staff_count"],
        "active_staff_session_count": len(staff_sessions),
        "active_pending_invite_count": len(active_pending_invites),
        "components": components,
        "production_blockers": blockers,
        "next_required_controls": next_required_controls,
        "limitation": (
            "Identity Readiness v1 is an externally reviewable prototype control "
            "summary. It does not integrate an external IdP, production MFA, "
            "distributed rate limiting, transactional delivery, or PostgreSQL."
        ),
    }


def _pre_pilot_check_status(status_value: str) -> str:
    if status_value in {"blocked", "blocker", "missing", "invalid"}:
        return "blocker"
    if status_value in {"review", "warning", "planned"}:
        return "warning"
    return "pass"


def _pre_pilot_readiness_response(repository: MicroScoreRepository) -> dict[str, Any]:
    security_readiness = _security_readiness_response(repository)
    identity_readiness = _identity_readiness_response(repository)
    delivery_readiness = _staff_invite_delivery_readiness_response(repository)
    adapter_readiness = _staff_invite_delivery_adapter_readiness_response()
    storage_readiness = repository.storage_readiness()
    postgresql_readiness = repository.postgresql_migration_readiness()
    active_model = repository.get_active_model_version()
    model_versions = repository.list_model_versions()
    applications = repository.list_applications()
    scored_applications = [
        application for application in applications if application.get("score_result")
    ]
    decided_applications = [
        application for application in applications if application.get("decision_result")
    ]
    simulations = repository.list_portfolio_simulations()
    latest_simulation = simulations[0] if simulations else None
    latest_simulation_summary = (
        _simulation_summary(latest_simulation) if latest_simulation else None
    )
    latest_simulation_scenarios = (
        set(latest_simulation_summary.get("scenarios", []))
        if latest_simulation_summary
        else set()
    )
    has_core_simulation_scenarios = {"baseline", "adverse", "severe"}.issubset(
        latest_simulation_scenarios
    )
    organizations = repository.list_organizations()

    checks: list[dict[str, Any]] = [
        {
            "key": "security_readiness",
            "label": "Security readiness gate",
            "category": "security",
            "status": _pre_pilot_check_status(security_readiness["status"]),
            "summary": (
                f"Security readiness is {security_readiness['status']} with "
                f"{security_readiness['blockers_count']} blocker(s) and "
                f"{security_readiness['warnings_count']} warning(s)."
            ),
            "action": (
                security_readiness["recommended_actions"][0]
                if security_readiness["recommended_actions"]
                else "Keep security readiness checks in the release gate."
            ),
            "evidence": {
                "status": security_readiness["status"],
                "blockers_count": security_readiness["blockers_count"],
                "warnings_count": security_readiness["warnings_count"],
                "check_keys": [check["key"] for check in security_readiness["checks"]],
            },
        },
        {
            "key": "identity_provider",
            "label": "Production identity and access",
            "category": "identity",
            "status": _pre_pilot_check_status(identity_readiness["status"]),
            "summary": (
                f"Identity readiness is {identity_readiness['status']}; "
                f"{len(identity_readiness['production_blockers'])} production "
                "blocker(s) remain."
            ),
            "action": (
                identity_readiness["next_required_controls"][0]["action"]
                if identity_readiness["next_required_controls"]
                else "Keep identity evidence current before pilot access."
            ),
            "evidence": {
                "auth_provider_mode": identity_readiness["auth_provider_mode"],
                "mfa_mode": identity_readiness["mfa_mode"],
                "session_control_mode": identity_readiness["session_control_mode"],
                "rate_limit_mode": identity_readiness["rate_limit_mode"],
                "production_blocker_keys": [
                    item["key"] for item in identity_readiness["production_blockers"]
                ],
            },
        },
        {
            "key": "transactional_delivery_adapter",
            "label": "Transactional invite delivery",
            "category": "delivery",
            "status": _pre_pilot_check_status(adapter_readiness["status"]),
            "summary": (
                f"Delivery adapter is {adapter_readiness['status']}; "
                f"external_send_enabled={adapter_readiness['external_send_enabled']} "
                f"and send_adapter_ready={adapter_readiness['send_adapter_ready']}."
            ),
            "action": (
                adapter_readiness["next_required_controls"][0]["action"]
                if adapter_readiness["next_required_controls"]
                else "Keep the adapter boundary blocked until a production sender exists."
            ),
            "evidence": {
                "provider": adapter_readiness["provider"],
                "adapter_mode": adapter_readiness["adapter_mode"],
                "configuration_status": adapter_readiness["configuration_status"],
                "secret_rotation_ready": adapter_readiness["secret_rotation_ready"],
                "blocker_keys": [item["key"] for item in adapter_readiness["blockers"]],
                "safe_payload_fields": adapter_readiness["safe_payload_fields"],
                "forbidden_payload_fields": adapter_readiness["forbidden_payload_fields"],
            },
        },
        {
            "key": "invite_delivery_evidence",
            "label": "Audited invite delivery evidence",
            "category": "delivery",
            "status": _pre_pilot_check_status(delivery_readiness["status"]),
            "summary": (
                f"Invite delivery readiness is {delivery_readiness['status']} using "
                f"{delivery_readiness['configured_provider']!r}; "
                f"{delivery_readiness['undelivered_active_invite_count']} active "
                "pending invite(s) lack delivery evidence."
            ),
            "action": (
                delivery_readiness["next_required_controls"][0]["action"]
                if delivery_readiness["next_required_controls"]
                else "Continue recording audited invite delivery attempts."
            ),
            "evidence": {
                "configured_provider": delivery_readiness["configured_provider"],
                "invite_url_https": delivery_readiness["invite_url_https"],
                "invite_url_local": delivery_readiness["invite_url_local"],
                "active_pending_invite_count": delivery_readiness[
                    "active_pending_invite_count"
                ],
                "undelivered_active_invite_count": delivery_readiness[
                    "undelivered_active_invite_count"
                ],
                "failed_latest_attempt_count": delivery_readiness[
                    "failed_latest_attempt_count"
                ],
            },
        },
        {
            "key": "storage_backend",
            "label": "Production storage backend",
            "category": "storage",
            "status": "pass" if postgresql_readiness["production_ready"] else "blocker",
            "summary": (
                f"Storage backend is {storage_readiness['backend']!r}; "
                f"PostgreSQL readiness is {postgresql_readiness['status']} with "
                f"{len(postgresql_readiness['blockers'])} blocker(s)."
            ),
            "action": (
                "Keep managed storage checks in release validation."
                if postgresql_readiness["production_ready"]
                else (
                    postgresql_readiness["next_required_controls"][0]["action"]
                    if postgresql_readiness["next_required_controls"]
                    else "Complete PostgreSQL migration readiness, backups, retention, and disposable integration tests."
                )
            ),
            "evidence": {
                "backend": storage_readiness["backend"],
                "production_ready": storage_readiness["production_ready"],
                "postgresql_migration_status": storage_readiness[
                    "postgresql_migration_status"
                ],
                "postgresql_readiness_status": postgresql_readiness["status"],
                "postgresql_repository_backend_status": postgresql_readiness[
                    "repository_backend_status"
                ],
                "postgresql_schema_inventory_table_count": postgresql_readiness[
                    "present_table_count"
                ],
                "postgresql_parity_check_count": len(
                    postgresql_readiness["parity_checks"]
                ),
                "postgresql_migration_artifact_count": postgresql_readiness[
                    "migration_artifact_count"
                ],
                "postgresql_latest_migration_version": postgresql_readiness[
                    "latest_migration_version"
                ],
                "postgresql_versioned_migration_contract_present": postgresql_readiness[
                    "versioned_migration_contract_present"
                ],
                "postgresql_disposable_migration_ci_present": postgresql_readiness[
                    "disposable_migration_ci_present"
                ],
                "postgresql_repository_adapter_contract_status": postgresql_readiness[
                    "repository_adapter_contract_status"
                ],
                "postgresql_repository_adapter_contract_method_count": postgresql_readiness[
                    "repository_adapter_contract_method_count"
                ],
                "postgresql_repository_adapter_implemented_method_count": postgresql_readiness[
                    "repository_adapter_implemented_method_count"
                ],
                "postgresql_repository_adapter_completed_method_group_count": postgresql_readiness[
                    "repository_adapter_completed_method_group_count"
                ],
                "postgresql_repository_adapter_completed_method_groups": postgresql_readiness[
                    "repository_adapter_completed_method_groups"
                ],
                "postgresql_repository_adapter_stage": postgresql_readiness[
                    "repository_adapter_stage"
                ],
                "postgresql_blocker_keys": [
                    item["key"] for item in postgresql_readiness["blockers"]
                ],
                "tenant_scoped_tables": storage_readiness["tenant_scoped_tables"],
            },
        },
        {
            "key": "model_registry",
            "label": "Model registry and validation boundary",
            "category": "model",
            "status": (
                "blocker"
                if active_model is None
                else "warning"
                if any(
                    "synthetic" in limitation.lower()
                    or "not validated" in limitation.lower()
                    for limitation in active_model.get("limitations") or []
                )
                else "pass"
            ),
            "summary": (
                "No active model version is registered."
                if active_model is None
                else (
                    f"Active model {active_model['version']!r} is registered with "
                    f"{len(active_model.get('limitations') or [])} limitation(s)."
                )
            ),
            "action": (
                "Register and activate a reviewed model version before scoring."
                if active_model is None
                else "Replace synthetic-only validation with permitted MFI/KZT calibration evidence before real pilot decisions."
            ),
            "evidence": {
                "active_model_version": active_model["version"] if active_model else None,
                "registered_model_count": len(model_versions),
                "feature_schema_version": (
                    active_model.get("feature_schema_version") if active_model else None
                ),
                "training_data_label": (
                    active_model.get("training_data_label") if active_model else None
                ),
            },
        },
        {
            "key": "monte_carlo_evidence",
            "label": "Monte Carlo portfolio stress evidence",
            "category": "simulation",
            "status": "pass" if has_core_simulation_scenarios else "warning",
            "summary": (
                "Latest saved Monte Carlo run includes baseline/adverse/severe scenarios."
                if has_core_simulation_scenarios
                else (
                    "No saved Monte Carlo run with baseline/adverse/severe scenarios "
                    "is available for the current release evidence."
                )
            ),
            "action": (
                "Keep seeded simulations reproducible and clearly labeled as scenario planning."
                if has_core_simulation_scenarios
                else "Run and save a seeded baseline/adverse/severe simulation before a reviewer demo."
            ),
            "evidence": {
                "simulation_count": len(simulations),
                "latest_simulation_id": (
                    latest_simulation_summary.get("simulation_id")
                    if latest_simulation_summary
                    else None
                ),
                "latest_scenarios": sorted(latest_simulation_scenarios),
                "latest_warning_count": (
                    latest_simulation_summary.get("warning_count")
                    if latest_simulation_summary
                    else None
                ),
            },
        },
        {
            "key": "review_flow_evidence",
            "label": "Borrower-to-analyst review flow",
            "category": "demo",
            "status": "pass" if scored_applications else "warning",
            "summary": (
                f"{len(applications)} application(s), {len(scored_applications)} "
                f"scored application(s), and {len(decided_applications)} recorded "
                "analyst decision(s) are present."
            ),
            "action": (
                "Keep borrower-safe status and MFI review packet smokes in the release gate."
                if scored_applications
                else "Submit and score a synthetic application before a reviewer demo."
            ),
            "evidence": {
                "application_count": len(applications),
                "scored_application_count": len(scored_applications),
                "decided_application_count": len(decided_applications),
            },
        },
        {
            "key": "privacy_data_boundary",
            "label": "Minimum-data and sensitive-field boundary",
            "category": "privacy",
            "status": "pass",
            "summary": (
                "Pilot data classes and forbidden data remain explicit; application intake "
                "requires consent and rejects secret-bearing/sensitive fields."
            ),
            "action": "Keep legal/privacy review ahead of any real borrower data collection.",
            "evidence": {
                "data_class_count": len(PILOT_DATA_CLASSES),
                "forbidden_data_count": len(FORBIDDEN_PILOT_DATA),
                "consent_required": True,
                "sensitive_field_rejection": True,
            },
        },
        {
            "key": "tenant_isolation",
            "label": "Organization-scoped MFI access",
            "category": "tenant",
            "status": "pass",
            "summary": (
                f"{len(organizations)} organization record(s); queues, review packets, "
                "analytics, simulations, and staff invites remain organization-scoped."
            ),
            "action": "Keep organization_id guards on every new MFI/admin surface.",
            "evidence": {
                "organization_count": len(organizations),
                "tenant_scoped_tables": storage_readiness["tenant_scoped_tables"],
            },
        },
    ]

    blockers = [check for check in checks if check["status"] == "blocker"]
    warnings = [check for check in checks if check["status"] == "warning"]
    passes = [check for check in checks if check["status"] == "pass"]
    readiness_score = max(0, min(100, 100 - len(blockers) * 15 - len(warnings) * 7))
    status_value = "blocked" if blockers else "review" if warnings else "ready"
    next_required_controls = [
        {
            "key": check["key"],
            "severity": "blocker" if check["status"] == "blocker" else "warning",
            "summary": check["summary"],
            "action": check["action"],
        }
        for check in blockers + warnings
    ]
    public_demo_allowed = bool(active_model and scored_applications)

    return {
        "status": status_value,
        "generated_at": _utc_now_iso(),
        "region": "Pavlodar region, Kazakhstan",
        "release_target": PRE_PILOT_RELEASE_TARGET,
        "blockers_count": len(blockers),
        "warnings_count": len(warnings),
        "passes_count": len(passes),
        "readiness_score": readiness_score,
        "production_data_allowed": not blockers and not warnings,
        "public_demo_allowed": public_demo_allowed,
        "checks": checks,
        "next_required_controls": next_required_controls,
        "signed_off_capabilities": [check["label"] for check in passes],
        "blocked_capabilities": [check["label"] for check in blockers],
        "limitation": PRE_PILOT_READINESS_LIMITATION,
    }


def _get_staff_invite_by_secret(
    repository: MicroScoreRepository,
    raw_token: str,
) -> dict[str, Any] | None:
    token_id = _staff_invite_token_id(raw_token)
    return repository.get_staff_invite(token_id) or repository.get_staff_invite(raw_token)


def _active_model_or_503(repository: MicroScoreRepository) -> dict[str, Any]:
    active_model = repository.get_active_model_version()
    if active_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scoring is disabled because no active model version is registered",
        )
    return active_model


def _model_governance_snapshot(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "lifecycle_status": model["lifecycle_status"],
        "feature_schema_version": model["feature_schema_version"],
        "training_data_label": model["training_data_label"],
        "random_state": model["random_state"],
        "activated_at": model.get("activated_at"),
        "limitations": list(model.get("limitations") or []),
    }


def _simulation_summary(record: dict[str, Any]) -> dict[str, Any]:
    result = record["result"]
    assumptions = result.get("assumptions") or {}
    policy = result.get("policy") or {}
    return {
        "simulation_id": record["id"],
        "generated_at": record["created_at"],
        "organization_id": record.get("organization_id"),
        "actor_email": record["actor_email"],
        "portfolio_fingerprint": record["portfolio_fingerprint"],
        "policy": policy.get("name", "balanced_review"),
        "iterations": assumptions.get("iterations", 0),
        "seed": assumptions.get("seed", 0),
        "scenarios": [row["scenario"] for row in result.get("scenarios") or []],
        "scored_application_count": result.get("scored_application_count", 0),
        "model_versions": list(result.get("model_versions") or []),
        "warning_count": len(result.get("warnings") or []),
        "scenario_summary": [
            {
                "scenario": row["scenario"],
                "probability_of_loss": row["probability_of_loss"],
                "portfolio_result_p50": row["portfolio_result"]["p50"],
            }
            for row in result.get("scenarios") or []
        ],
    }


def _simulation_for_user(
    simulation_id: str,
    user: dict[str, Any],
    repository: MicroScoreRepository,
) -> dict[str, Any]:
    record = repository.get_portfolio_simulation(simulation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio simulation not found",
        )
    if user["role"] != "admin" and record.get("organization_id") != _mfi_organization_scope(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return record


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    user = repository.get_user_by_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def require_mfi_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] not in {"mfi_analyst", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFI access required")
    return user


def require_admin_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _mfi_organization_scope(user: dict[str, Any]) -> str | None:
    if user["role"] == "admin":
        return None
    organization_id = user.get("organization_id")
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFI analyst is not assigned to an organization",
        )
    return str(organization_id)


def _application_for_user(
    application_id: str,
    user: dict[str, Any],
    repository: MicroScoreRepository,
) -> dict[str, Any]:
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    is_owner = application["borrower_email"] == user["email"]
    can_review = user["role"] == "admin" or (
        user["role"] == "mfi_analyst"
        and user.get("organization_id") == application.get("organization_id")
    )
    if not is_owner and not can_review:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return application


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_application_privacy(payload: ApplicationCreate) -> str:
    if not payload.consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Confirm synthetic-data consent before submitting an application",
        )

    consent_version = (payload.consent_version or "").strip()
    if not consent_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A consent version is required for auditability",
        )

    signal_values = payload.behavioral_signals.model_dump(exclude_none=True)
    forbidden_paths = find_forbidden_signal_paths(signal_values)
    if forbidden_paths:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Remove sensitive personal fields before submitting",
                "forbidden_fields": forbidden_paths,
            },
        )
    return consent_version


def _timeline_title(action: str, details: dict[str, Any] | None = None) -> str:
    details = details or {}
    if action == "application_decision_recorded":
        decision_titles = {
            "review": "Application moved to manual review",
            "approve": "Application approved",
            "decline": "Application declined",
        }
        decision = str(details.get("decision") or "")
        if decision in decision_titles:
            return decision_titles[decision]
    titles = {
        "application_created": "Application submitted",
        "application_scored": "Risk score generated",
        "application_rescored": "Risk score refreshed",
        "application_decision_recorded": "Analyst decision recorded",
    }
    return titles.get(action, action.replace("_", " ").title())


def _timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    details = event.get("details") or {}
    return {
        "id": event["id"],
        "action": event["action"],
        "title": _timeline_title(event["action"], details),
        "actor_email": event.get("actor_email"),
        "details": details,
        "created_at": event["created_at"],
    }


BORROWER_STATUS_MESSAGES = {
    "submitted": "Application received. It is waiting for MFI scoring.",
    "scored": "Risk assessment completed. It is waiting for analyst review.",
    "under_review": "An MFI analyst is reviewing the application.",
    "approved": "The MFI recorded an approval decision.",
    "declined": "The MFI recorded a decline decision.",
}


def _borrower_application(application: dict[str, Any]) -> dict[str, Any]:
    status_value = str(application["status"])
    return {
        "id": application["id"],
        "status": status_value,
        "requested_amount": application["requested_amount"],
        "purpose": application["purpose"],
        "district": application.get("district"),
        "settlement_type": application.get("settlement_type"),
        "organization_id": application.get("organization_id"),
        "created_at": application["created_at"],
        "scored_at": application.get("scored_at"),
        "status_message": BORROWER_STATUS_MESSAGES[status_value],
        "terminal": status_value in {"approved", "declined"},
    }


def _borrower_timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    projected = _timeline_event(event)
    status_value = projected["details"].get("status")
    projected["actor_email"] = None
    projected["details"] = {"status": status_value} if status_value else {}
    return projected


MFI_LIFECYCLE_NOTES = {
    "submitted": "Application is ready for its first governed score.",
    "scored": "Score is available; complete human review before a final decision.",
    "under_review": "Manual review is open; record approve or decline after checks.",
    "approved": "Approval is terminal in the prototype and cannot be silently reversed.",
    "declined": "Decline is terminal in the prototype and cannot be silently reversed.",
}


def _application_lifecycle_summary(application: dict[str, Any]) -> dict[str, Any]:
    status_value = str(application["status"])
    terminal = status_value in {"approved", "declined"}
    if status_value == "submitted":
        scoring_action = "score"
        allowed_decisions: list[str] = []
    elif status_value == "scored":
        scoring_action = "rescore"
        allowed_decisions = ["review", "approve", "decline"]
    elif status_value == "under_review":
        scoring_action = "rescore"
        allowed_decisions = ["approve", "decline"]
    else:
        scoring_action = None
        allowed_decisions = []
    return {
        "status": status_value,
        "terminal": terminal,
        "scoring_action": scoring_action,
        "allowed_decisions": allowed_decisions,
        "status_note": MFI_LIFECYCLE_NOTES[status_value],
    }


def _optional_nonnegative_number(signals: dict[str, Any], field: str) -> float | None:
    value = signals.get(field)
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _affordability_snapshot(application: dict[str, Any]) -> dict[str, Any]:
    signals = application.get("behavioral_signals") or {}
    annual_income = _optional_nonnegative_number(signals, "annual_income")
    outstanding_debt = _optional_nonnegative_number(signals, "total_outstanding_debt")
    open_loans_value = _optional_nonnegative_number(signals, "num_open_loans")
    open_loans = int(open_loans_value) if open_loans_value is not None else None
    requested_amount = float(application["requested_amount"])
    required = {
        "annual_income": annual_income,
        "total_outstanding_debt": outstanding_debt,
        "num_open_loans": open_loans_value,
    }
    missing_fields = [field for field, value in required.items() if value is None]
    income_denominator = annual_income if annual_income and annual_income > 0 else None
    return {
        "annual_income": annual_income,
        "total_outstanding_debt": outstanding_debt,
        "num_open_loans": open_loans,
        "debt_to_income_ratio": (
            outstanding_debt / income_denominator
            if outstanding_debt is not None and income_denominator
            else None
        ),
        "requested_amount_to_income_ratio": (
            requested_amount / income_denominator if income_denominator else None
        ),
        "completeness": (len(required) - len(missing_fields)) / len(required),
        "missing_fields": missing_fields,
        "note": (
            "Screening indicators only. Income period, loan term, expenses, and verified "
            "cash flow are required before any real affordability conclusion."
        ),
    }


def _review_packet(
    application: dict[str, Any],
    timeline_events: list[dict[str, Any]] | None = None,
    active_model_version: str | None = None,
    decision_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    score = application.get("score_result")
    decision = application.get("decision_result")
    governance_flags = _review_governance_flags(application, active_model_version)

    return {
        "application_id": application["id"],
        "generated_at": _utc_now_iso(),
        "application": {
            "id": application["id"],
            "borrower_email": application["borrower_email"],
            "status": application["status"],
            "requested_amount": application["requested_amount"],
            "purpose": application["purpose"],
            "district": application.get("district"),
            "settlement_type": application.get("settlement_type"),
            "organization_id": application.get("organization_id"),
            "created_at": application["created_at"],
            "scored_at": application.get("scored_at"),
        },
        "model_summary": _review_model_summary(score, active_model_version),
        "decision_support": (score or {}).get("decision_support") if score else None,
        "analyst_decision": decision,
        "decision_history": decision_history or [],
        "lifecycle": _application_lifecycle_summary(application),
        "affordability": _affordability_snapshot(application),
        "timeline_events": timeline_events or [],
        "scenario_scores": (score or {}).get("scenario_scores") or [],
        "top_risk_factors": _top_explanation_factors(score, "top_positive_factors"),
        "top_protective_factors": _top_explanation_factors(score, "top_protective_factors"),
        "governance_flags": governance_flags,
        "checklist": _review_checklist(application, governance_flags),
        "audit_note": (
            "Review packet summarizes model output and analyst workflow only. "
            "It is not a legal credit decision record and does not contain "
            "validated repayment outcomes."
        ),
    }


def _review_model_summary(
    score: dict[str, Any] | None,
    active_model_version: str | None = None,
) -> dict[str, Any] | None:
    if not score:
        return None
    governance = score.get("model_governance") or {}
    return {
        "model_name": score.get("model_name", "unknown"),
        "model_version": score.get("model_version", "unknown"),
        "feature_schema_version": governance.get("feature_schema_version"),
        "training_data_label": governance.get("training_data_label"),
        "activated_at": governance.get("activated_at"),
        "is_current_active": (
            active_model_version is None
            or score.get("model_version") == active_model_version
        ),
        "risk_band": score.get("risk_band"),
        "high_risk_probability": score.get("high_risk_probability"),
        "proxy_sensitivity_delta": score.get("proxy_sensitivity_delta"),
        "missing_feature_count": score.get("missing_feature_count", 0),
    }


def _top_explanation_factors(
    score: dict[str, Any] | None,
    field_name: str,
) -> list[dict[str, Any]]:
    explanation = (score or {}).get("explanation") or {}
    return list(explanation.get(field_name) or [])[:5]


def _review_governance_flags(
    application: dict[str, Any],
    active_model_version: str | None = None,
) -> list[str]:
    score = application.get("score_result")
    flags: list[str] = []
    if score is None:
        flags.append("score_not_available")
        return flags

    if application.get("decision_result") is None:
        flags.append("human_decision_not_recorded")
    if score.get("risk_band") == "high":
        flags.append("high_risk_application")
    if (score.get("proxy_sensitivity_delta") or 0) >= 0.2:
        flags.append("proxy_sensitive_score")
    if score.get("missing_feature_count", 0) > 0:
        flags.append("missing_model_features")
    if (
        active_model_version is not None
        and score.get("model_version") != active_model_version
    ):
        flags.append("stale_model_version")

    recommendation = score.get("decision_support") or {}
    if recommendation.get("recommendation_code") == "manual_review_proxy_sensitive":
        flags.append("manual_review_proxy_sensitive")
    return flags


def _review_checklist(
    application: dict[str, Any],
    governance_flags: list[str],
) -> list[dict[str, str]]:
    score = application.get("score_result")
    decision = application.get("decision_result")
    checklist = [
        {
            "code": "verify_identity",
            "title": "Verify borrower identity and application ownership",
            "status": "suggested",
            "evidence": application["borrower_email"],
        },
        {
            "code": "verify_affordability",
            "title": "Review income stability and repayment affordability",
            "status": "required" if score else "suggested",
            "evidence": application.get("purpose") or None,
        },
    ]

    if "proxy_sensitive_score" in governance_flags:
        checklist.append(
            {
                "code": "review_proxy_context",
                "title": "Review late-payment context before declining",
                "status": "required",
                "evidence": "proxy_sensitivity_delta >= 0.20",
            }
        )
    if "high_risk_application" in governance_flags:
        checklist.append(
            {
                "code": "senior_review",
                "title": "Escalate high-risk cases before approval",
                "status": "required",
                "evidence": "risk_band=high",
            }
        )
    if "stale_model_version" in governance_flags:
        checklist.append(
            {
                "code": "rescore_current_model",
                "title": "Re-score with the currently active model before decision",
                "status": "required",
                "evidence": f"scored_with={score.get('model_version') if score else 'unknown'}",
            }
        )
    checklist.append(
        {
            "code": "record_human_decision",
            "title": "Record analyst decision and review note",
            "status": "complete" if decision else "required",
            "evidence": (decision or {}).get("note") if decision else None,
        }
    )
    return checklist


PORTFOLIO_EXPORT_FIELDS = (
    "application_id",
    "organization_id",
    "borrower_email",
    "status",
    "created_at",
    "scored_at",
    "requested_amount",
    "purpose",
    "district",
    "settlement_type",
    "risk_band",
    "high_risk_probability",
    "proxy_sensitivity_delta",
    "recommendation_code",
    "recommendation_title",
    "decision",
    "policy_name",
    "decision_note",
    "decision_created_at",
    "governance_flags",
)

# Boring on purpose: this is the guardrail that keeps a future pilot from
# quietly turning into "please upload every private thing you have".
PILOT_DATA_CLASSES = [
    {
        "data_class": "Internal borrower id",
        "collect_in_pilot": "yes",
        "model_use": "no",
        "notes": "Use a random pilot id, not an IIN or passport number.",
    },
    {
        "data_class": "District and settlement type",
        "collect_in_pilot": "yes",
        "model_use": "yes, with caution",
        "notes": "Needed to validate Pavlodar regional assumptions.",
    },
    {
        "data_class": "Income and debt bands",
        "collect_in_pilot": "yes",
        "model_use": "yes",
        "notes": "Prefer bands over exact values in the first supervised pilot.",
    },
    {
        "data_class": "Late payment count",
        "collect_in_pilot": "yes",
        "model_use": "yes, flagged",
        "notes": "Strong proxy feature; every report must audit its influence.",
    },
    {
        "data_class": "Digital banking activity",
        "collect_in_pilot": "yes",
        "model_use": "yes",
        "notes": "Use summarized counts or bands, not raw transaction logs.",
    },
    {
        "data_class": "Gender",
        "collect_in_pilot": "optional",
        "model_use": "audit only",
        "notes": "Use for fairness review, not as a model input by default.",
    },
    {
        "data_class": "Employment type",
        "collect_in_pilot": "yes",
        "model_use": "yes and audit",
        "notes": "Useful for segment stability and fairness checks.",
    },
]

FORBIDDEN_PILOT_DATA = [
    "IINs, passport numbers, or national ID images",
    "raw bank statements",
    "raw card transaction descriptions",
    "precise geolocation",
    "social media contacts or phone-book data",
    "device fingerprinting",
    "photos, biometric data, or voice recordings",
]

PILOT_VALIDATION_QUESTIONS = [
    "Which fields can an MFI provide legally and ethically?",
    "Which fields are already available in summarized form?",
    "Which fields require explicit borrower consent?",
    "Does late_payment_count remain a dominant proxy on real data?",
    "Which segments show higher false positive or false negative rates?",
]

PILOT_SUCCESS_CRITERIA = [
    "consented, minimal, non-invasive data collection",
    "no use of direct identity fields as model features",
    "reproducible model and feature-schema versioning",
    "calibrated probability review, not only ROC-AUC",
    "segment/fairness reporting by gender, employment type, and district",
    "analyst feedback on whether explanations are understandable",
]

PRE_PILOT_RELEASE_TARGET = (
    "public portfolio demo and controlled MFI validation planning, not real borrower onboarding"
)
PRE_PILOT_READINESS_LIMITATION = (
    "Pre-Pilot Readiness Gate v1 aggregates live prototype evidence for release planning. "
    "It does not grant permission to collect real borrower data; production IdP/TOTP/WebAuthn, "
    "managed PostgreSQL, real KZT calibration, legal/privacy sign-off, and transactional "
    "invite delivery must be completed before a real pilot."
)


def _portfolio_export_csv(applications: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=PORTFOLIO_EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    for application in applications:
        writer.writerow(_portfolio_export_row(application))
    return output.getvalue()


def _portfolio_export_row(application: dict[str, Any]) -> dict[str, Any]:
    score = application.get("score_result") or {}
    decision_support = score.get("decision_support") or {}
    decision = application.get("decision_result") or {}
    governance_flags = _review_governance_flags(application)
    return {
        "application_id": application["id"],
        "organization_id": application.get("organization_id") or "",
        "borrower_email": application["borrower_email"],
        "status": application["status"],
        "created_at": application["created_at"],
        "scored_at": application.get("scored_at") or "",
        "requested_amount": application["requested_amount"],
        "purpose": application["purpose"],
        "district": application.get("district") or "",
        "settlement_type": application.get("settlement_type") or "",
        "risk_band": score.get("risk_band") or "",
        "high_risk_probability": score.get("high_risk_probability") or "",
        "proxy_sensitivity_delta": score.get("proxy_sensitivity_delta") or "",
        "recommendation_code": decision_support.get("recommendation_code") or "",
        "recommendation_title": decision_support.get("title") or "",
        "decision": decision.get("decision") or "",
        "policy_name": decision.get("policy_name") or "",
        "decision_note": decision.get("note") or "",
        "decision_created_at": decision.get("created_at") or "",
        "governance_flags": ";".join(governance_flags),
    }


@app.get("/health", response_model=HealthResponse)
def health(repository: MicroScoreRepository = Depends(get_repository)) -> HealthResponse:
    return {
        "status": "ok",
        "service": "microscore-api",
        "database": str(repository.db_path),
        "storage": repository.storage_readiness(),
    }


@app.get("/governance/pilot-readiness", response_model=PilotReadinessResponse)
def pilot_readiness() -> PilotReadinessResponse:
    return {
        "status": "planning_only",
        "region": "Pavlodar region, Kazakhstan",
        "privacy_note": (
            "MicroScore is not running a real borrower pilot yet. This contract "
            "defines a future minimum-data pilot and explicitly excludes direct "
            "identity fields from model inputs."
        ),
        "data_classes": PILOT_DATA_CLASSES,
        "forbidden_data": FORBIDDEN_PILOT_DATA,
        "validation_questions": PILOT_VALIDATION_QUESTIONS,
        "first_pilot_success_criteria": PILOT_SUCCESS_CRITERIA,
    }


@app.get("/organizations", response_model=list[OrganizationPublic])
def list_public_organizations(
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_organizations()


@app.post("/auth/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    repository: MicroScoreRepository = Depends(get_repository),
) -> AuthResponse:
    email = payload.email.strip().lower()
    if payload.role != "borrower":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is limited to borrower accounts",
        )

    _validate_new_password(payload.password)

    token = create_token()

    try:
        repository.create_user(email, hash_password(payload.password), payload.role)
    except DuplicateUserError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    session = repository.create_session(token, email)
    return AuthResponse(
        access_token=token,
        role=payload.role,
        organization_id=None,
        session_expires_at=session["session_expires_at"],
        session_ttl_seconds=session["session_ttl_seconds"],
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    repository: MicroScoreRepository = Depends(get_repository),
    limiter: LoginRateLimiter = Depends(get_login_rate_limiter),
) -> AuthResponse:
    email = payload.email.strip().lower()
    rate_key = _login_rate_key(request, email)
    retry_after = limiter.retry_after(rate_key)
    if retry_after:
        _raise_login_rate_limit(retry_after)

    user = repository.get_user(email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        retry_after = limiter.record_failure(rate_key)
        if retry_after:
            _raise_login_rate_limit(retry_after)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.get("disabled_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )
    try:
        mfa_verified = _verify_staff_mfa_for_session(user, payload.mfa_code)
    except HTTPException as exc:
        if user["role"] in MFA_REQUIRED_ROLES:
            _record_staff_mfa_challenge_failed(
                repository,
                actor_email=email,
                entity_type="user",
                entity_id=email,
                reason=_staff_mfa_failure_reason_from_exception(exc),
                source="login",
                mfa_code=payload.mfa_code,
                method=user.get("mfa_method") or "prototype_mfa_code",
                details={
                    "role": user["role"],
                    "organization_id": user.get("organization_id"),
                },
            )
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            retry_after = limiter.record_failure(rate_key)
            if retry_after:
                _raise_login_rate_limit(retry_after)
        raise

    limiter.record_success(rate_key)
    token = create_token()
    session = repository.create_session(token, email)
    if mfa_verified:
        repository.record_audit_event(
            actor_email=email,
            action="staff_mfa_login_verified",
            entity_type="user",
            entity_id=email,
            details={
                "method": user.get("mfa_method") or "prototype_mfa_code",
                "prototype": True,
            },
        )
    return AuthResponse(
        access_token=token,
        role=user["role"],
        organization_id=user.get("organization_id"),
        session_expires_at=session["session_expires_at"],
        session_ttl_seconds=session["session_ttl_seconds"],
    )


@app.post("/auth/accept-staff-invite", response_model=AuthResponse)
def accept_staff_invite(
    payload: StaffInviteAccept,
    repository: MicroScoreRepository = Depends(get_repository),
) -> AuthResponse:
    token = payload.token.strip()
    invite = _get_staff_invite_by_secret(repository, token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    token_id = invite["token"]
    if invite.get("accepted_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff invite has already been accepted",
        )
    if invite.get("revoked_at"):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Staff invite has been revoked",
        )
    if _parse_utc_datetime(invite["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Staff invite has expired",
        )

    _validate_new_password(payload.password)
    try:
        _verify_invite_acceptance_mfa(invite["role"], payload.mfa_code)
    except HTTPException as exc:
        if invite["role"] in MFA_REQUIRED_ROLES:
            _record_staff_mfa_challenge_failed(
                repository,
                actor_email=invite["email"],
                entity_type="staff_invite",
                entity_id=token_id,
                reason=_staff_mfa_failure_reason_from_exception(exc),
                source="staff_invite_acceptance",
                mfa_code=payload.mfa_code,
                method="prototype_mfa_code",
                details={
                    "email": invite["email"],
                    "role": invite["role"],
                    "organization_id": invite["organization_id"],
                    "token_preview": _staff_invite_token_preview(token_id),
                },
            )
        raise
    email = invite["email"].strip().lower()
    if repository.get_user(email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    try:
        created = repository.create_user(
            email,
            hash_password(payload.password),
            invite["role"],
            invite["organization_id"],
        )
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )
    accepted = repository.mark_staff_invite_accepted(token_id, email)
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff invite has already been accepted",
        )

    repository.record_audit_event(
        actor_email=email,
        action="staff_invite_accepted",
        entity_type="staff_invite",
        entity_id=token_id,
        details={
            "email": email,
            "role": created["role"],
            "organization_id": created.get("organization_id"),
            "token_preview": _staff_invite_token_preview(token_id),
        },
    )
    attested = repository.attest_user_mfa(email, email, "prototype_mfa_code")
    repository.record_audit_event(
        actor_email=email,
        action="staff_mfa_attested",
        entity_type="user",
        entity_id=email,
        details={
            "method": attested.get("mfa_method") or "prototype_mfa_code",
            "source": "staff_invite_acceptance",
            "was_already_attested": attested.get("was_already_attested", False),
            "limitation": MFA_READINESS_LIMITATION,
        },
    )
    access_token = create_token()
    session = repository.create_session(access_token, email)
    repository.record_audit_event(
        actor_email=email,
        action="staff_mfa_login_verified",
        entity_type="user",
        entity_id=email,
        details={
            "method": "prototype_mfa_code",
            "prototype": True,
            "source": "staff_invite_acceptance",
        },
    )
    return AuthResponse(
        access_token=access_token,
        role=created["role"],
        organization_id=created.get("organization_id"),
        session_expires_at=session["session_expires_at"],
        session_ttl_seconds=session["session_ttl_seconds"],
    )


@app.post("/auth/logout", response_model=LogoutResponse)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> LogoutResponse:
    revoked = repository.revoke_session(credentials.credentials)
    repository.record_audit_event(
        actor_email=user["email"],
        action="user_logged_out",
        entity_type="session",
        entity_id=user["email"],
        details={"role": user["role"]},
    )
    return LogoutResponse(revoked=revoked)


@app.get("/me", response_model=MeResponse)
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {
        "email": user["email"],
        "role": user["role"],
        "organization_id": user.get("organization_id"),
        "created_at": user["created_at"],
        "disabled_at": user.get("disabled_at"),
        "disabled_by": user.get("disabled_by"),
        "mfa_attested_at": user.get("mfa_attested_at"),
        "mfa_attested_by": user.get("mfa_attested_by"),
        "mfa_method": user.get("mfa_method"),
        "session_expires_at": user["session_expires_at"],
        "session_ttl_seconds": user["session_ttl_seconds"],
    }


@app.post("/applications", response_model=BorrowerApplicationResponse)
def create_application(
    payload: ApplicationCreate,
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    if user["role"] != "borrower":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Borrower account required")

    consent_version = _validate_application_privacy(payload)
    if repository.get_organization(payload.organization_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select a valid MFI organization",
        )
    application_id = str(uuid4())
    features = payload.behavioral_signals.model_dump(exclude_none=True)
    features["loan_application_amount"] = payload.requested_amount
    if payload.district:
        features["pavlodar_district"] = payload.district
    if payload.settlement_type:
        features["settlement_type"] = payload.settlement_type

    application = repository.create_application(
        application_id=application_id,
        borrower_email=user["email"],
        requested_amount=payload.requested_amount,
        purpose=payload.purpose,
        district=payload.district,
        settlement_type=payload.settlement_type,
        behavioral_signals=features,
        consent_version=consent_version,
        organization_id=payload.organization_id,
    )
    return _borrower_application(application)


@app.get("/applications", response_model=list[BorrowerApplicationResponse])
def list_borrower_applications(
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    if user["role"] != "borrower":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Borrower account required",
        )
    return [
        _borrower_application(application)
        for application in repository.list_borrower_applications(user["email"])
    ]


@app.get("/applications/{application_id}", response_model=BorrowerApplicationResponse)
def get_application(
    application_id: str,
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    if user["role"] != "borrower":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Borrower account required",
        )
    return _borrower_application(_application_for_user(application_id, user, repository))


@app.get(
    "/applications/{application_id}/timeline",
    response_model=list[ApplicationTimelineEventResponse],
)
def application_timeline(
    application_id: str,
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    _application_for_user(application_id, user, repository)
    projector = _borrower_timeline_event if user["role"] == "borrower" else _timeline_event
    return [
        projector(event)
        for event in repository.list_application_timeline(application_id)
    ]


@app.get("/mfi/applications", response_model=list[LoanApplicationResponse])
def list_mfi_applications(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_applications(_mfi_organization_scope(user))


@app.get("/mfi/model-status", response_model=ModelStatusResponse)
def mfi_model_status(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    active_model = repository.get_active_model_version()
    return {
        "scoring_allowed": active_model is not None,
        "active_model": active_model,
        "note": (
            "Active model is registered for decision support only; human review remains required."
            if active_model
            else "Scoring is disabled until an administrator activates a model version."
        ),
    }


@app.get("/mfi/applications/export.csv")
def export_mfi_applications(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> Response:
    csv_text = _portfolio_export_csv(
        repository.list_applications(_mfi_organization_scope(user))
    )
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="microscore-applications.csv"',
        },
    )


@app.post("/mfi/applications/{application_id}/score", response_model=LoanApplicationResponse)
def score_application(
    application_id: str,
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    application = _application_for_user(application_id, user, repository)
    if application["status"] in {"approved", "declined"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot score an application after it is {application['status']}",
        )

    active_model = _active_model_or_503(repository)
    score = get_scoring_service(
        active_model["model_name"],
        active_model["version"],
        active_model["random_state"],
    ).score(application["behavioral_signals"])
    score_result = asdict(score)
    score_result["model_governance"] = _model_governance_snapshot(active_model)
    try:
        updated = repository.update_application_score(
            application_id=application_id,
            score_result=score_result,
            actor_email=user["email"],
        )
    except InvalidApplicationTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return updated


@app.post("/mfi/applications/{application_id}/decision", response_model=LoanApplicationResponse)
def record_application_decision(
    application_id: str,
    payload: ApplicationDecisionCreate,
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    application = _application_for_user(application_id, user, repository)
    if application.get("score_result") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Score the application before recording an MFI decision",
        )

    try:
        updated = repository.record_application_decision(
            application_id=application_id,
            actor_email=user["email"],
            decision=payload.decision,
            policy_name=payload.policy_name,
            note=payload.note.strip(),
        )
    except InvalidApplicationTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return updated


@app.get(
    "/mfi/applications/{application_id}/review-packet",
    response_model=ApplicationReviewPacketResponse,
)
def application_review_packet(
    application_id: str,
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    application = _application_for_user(application_id, user, repository)
    timeline = [
        _timeline_event(event)
        for event in repository.list_application_timeline(application_id)
    ]
    active_model = repository.get_active_model_version()
    return _review_packet(
        application,
        timeline,
        active_model["version"] if active_model else None,
        repository.list_application_decisions(application_id),
    )


@app.get("/mfi/analytics/segments", response_model=list[SegmentAnalyticsRow])
def segment_analytics(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.segment_analytics(_mfi_organization_scope(user))


@app.get("/mfi/analytics/policies", response_model=PolicyAnalyticsResponse)
def policy_analytics(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return build_policy_analytics(
        repository.list_applications(_mfi_organization_scope(user))
    )


@app.post(
    "/mfi/simulations/portfolio",
    response_model=PortfolioSimulationResponse,
)
def portfolio_monte_carlo_simulation(
    payload: PortfolioSimulationRequest,
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    organization_id = _mfi_organization_scope(user)
    try:
        result = simulate_portfolio(
            repository.list_applications(organization_id),
            iterations=payload.iterations,
            seed=payload.seed,
            policy_name=payload.policy,
            scenarios=tuple(payload.scenarios),
            review_approval_rate=payload.review_approval_rate,
            interest_margin_rate=payload.interest_margin_rate,
            loss_given_default=payload.loss_given_default,
            operating_cost_per_approved=payload.operating_cost_per_approved,
            macro_volatility=payload.macro_volatility,
            calibration_volatility=payload.calibration_volatility,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    active_model = repository.get_active_model_version()
    active_version = (active_model or {}).get("version")
    stale_versions = [
        version
        for version in result["model_versions"]
        if active_version is not None and version != active_version
    ]
    if stale_versions:
        result["warnings"].append(
            "Portfolio includes scores that are not from the active model version "
            f"{active_version}: {', '.join(stale_versions)}."
        )

    simulation_id = str(uuid4())
    response = {
        "simulation_id": simulation_id,
        "generated_at": _utc_now_iso(),
        "organization_id": organization_id,
        "actor_email": user["email"],
        **result,
    }
    repository.create_portfolio_simulation(
        simulation_id=simulation_id,
        organization_id=organization_id,
        actor_email=user["email"],
        portfolio_fingerprint=result["portfolio_fingerprint"],
        request_payload=payload.model_dump(mode="json"),
        result_payload=response,
        created_at=response["generated_at"],
    )
    repository.record_audit_event(
        actor_email=user["email"],
        action="portfolio_simulation_run",
        entity_type="portfolio_simulation",
        entity_id=simulation_id,
        details={
            "organization_id": organization_id,
            "policy": payload.policy,
            "iterations": payload.iterations,
            "seed": payload.seed,
            "scenarios": list(payload.scenarios),
            "scored_application_count": result["scored_application_count"],
            "model_versions": result["model_versions"],
            "scenario_summary": [
                {
                    "scenario": row["scenario"],
                    "probability_of_loss": row["probability_of_loss"],
                    "portfolio_result_p50": row["portfolio_result"]["p50"],
                }
                for row in result["scenarios"]
            ],
        },
    )
    return response


@app.get("/mfi/simulations", response_model=list[PortfolioSimulationSummary])
def list_portfolio_simulations(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    records = repository.list_portfolio_simulations(_mfi_organization_scope(user))
    return [_simulation_summary(record) for record in records]


@app.get(
    "/mfi/simulations/{simulation_id}",
    response_model=PortfolioSimulationResponse,
)
def get_portfolio_simulation(
    simulation_id: str,
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _simulation_for_user(simulation_id, user, repository)["result"]


@app.get("/mfi/analytics/decisions", response_model=DecisionAnalyticsResponse)
def decision_analytics(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return repository.decision_analytics(_mfi_organization_scope(user))


@app.get("/admin/audit-events", response_model=list[AuditEventResponse])
def audit_events(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_audit_events()


@app.get(
    "/admin/governance/pre-pilot-readiness",
    response_model=PrePilotReadinessResponse,
)
def admin_pre_pilot_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _pre_pilot_readiness_response(repository)


@app.get(
    "/admin/storage/postgresql-readiness",
    response_model=PostgresMigrationReadinessResponse,
)
def admin_postgresql_migration_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return repository.postgresql_migration_readiness()


@app.get("/admin/users", response_model=list[UserPublic])
def list_admin_users(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_users()


@app.get("/admin/security/readiness", response_model=SecurityReadinessResponse)
def security_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _security_readiness_response(repository)


@app.get("/admin/security/identity-readiness", response_model=IdentityReadinessResponse)
def identity_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _identity_readiness_response(repository)


@app.get("/admin/security/mfa-readiness", response_model=MfaReadinessResponse)
def mfa_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _mfa_readiness_response(repository.list_users())


@app.post("/admin/users/{email}/mfa/attest", response_model=MfaAttestationResponse)
def attest_staff_mfa(
    email: str,
    payload: MfaAttestationCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    target_email = email.strip().lower()
    target = repository.get_user(target_email)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if target["role"] not in MFA_REQUIRED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active staff accounts require MFA attestation",
        )
    if target.get("disabled_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disabled staff accounts do not require MFA attestation",
        )

    attested = repository.attest_user_mfa(target_email, user["email"], payload.method)
    if attested is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not attested["was_already_attested"]:
        repository.record_audit_event(
            actor_email=user["email"],
            action="staff_mfa_attested",
            entity_type="user",
            entity_id=target_email,
            details={
                "role": target["role"],
                "organization_id": target.get("organization_id"),
                "method": payload.method,
                "limitation": MFA_READINESS_LIMITATION,
            },
        )
    return attested


@app.post("/admin/users/{email}/disable", response_model=StaffUserDisableResponse)
def disable_staff_user(
    email: str,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    target_email = email.strip().lower()
    target = repository.get_user(target_email)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if target["role"] != "mfi_analyst":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only MFI analyst accounts can be disabled here",
        )

    disabled = repository.disable_user(target_email, user["email"])
    if disabled is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not disabled["was_already_disabled"]:
        repository.record_audit_event(
            actor_email=user["email"],
            action="staff_user_disabled",
            entity_type="user",
            entity_id=target_email,
            details={
                "role": target["role"],
                "organization_id": target.get("organization_id"),
                "revoked_session_count": disabled["revoked_session_count"],
            },
        )
    return disabled


@app.post("/admin/users/{email}/reactivate", response_model=StaffUserReactivateResponse)
def reactivate_staff_user(
    email: str,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    target_email = email.strip().lower()
    target = repository.get_user(target_email)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if target["role"] != "mfi_analyst":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only MFI analyst accounts can be reactivated here",
        )

    reactivated = repository.reactivate_user(target_email)
    if reactivated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not reactivated["was_already_active"]:
        repository.record_audit_event(
            actor_email=user["email"],
            action="staff_user_reactivated",
            entity_type="user",
            entity_id=target_email,
            details={
                "role": target["role"],
                "organization_id": target.get("organization_id"),
                "previous_disabled_at": reactivated["previous_disabled_at"],
                "previous_disabled_by": reactivated["previous_disabled_by"],
            },
        )
    return reactivated


@app.get("/admin/staff-sessions", response_model=list[StaffSessionResponse])
def list_staff_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    current_session_id = _session_id_for_token(credentials.credentials)
    return [
        _staff_session_response(session, current_session_id=current_session_id)
        for session in repository.list_active_sessions(staff_only=True)
    ]


@app.delete(
    "/admin/staff-sessions/{session_id}",
    response_model=StaffSessionRevokeResponse,
)
def revoke_staff_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    normalized_session_id = session_id.strip().lower()
    if normalized_session_id == _session_id_for_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Current admin session cannot be revoked from this endpoint; use logout.",
        )

    revoked_session = repository.revoke_session_by_id(
        normalized_session_id,
        staff_only=True,
    )
    if revoked_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff session not found",
        )
    repository.record_audit_event(
        actor_email=user["email"],
        action="staff_session_revoked",
        entity_type="session",
        entity_id=normalized_session_id,
        details={
            "session_preview": f"{normalized_session_id[:12]}...",
            "email": revoked_session["email"],
            "role": revoked_session["role"],
            "organization_id": revoked_session.get("organization_id"),
            "session_created_at": revoked_session["session_created_at"],
            "session_expires_at": revoked_session["session_expires_at"],
        },
    )
    return {
        "revoked": True,
        "session_id": normalized_session_id,
        "email": revoked_session["email"],
        "role": revoked_session["role"],
        "organization_id": revoked_session.get("organization_id"),
    }


@app.get("/admin/staff-invites", response_model=list[StaffInviteResponse])
def list_staff_invites(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [_staff_invite_response(invite) for invite in repository.list_staff_invites()]


@app.get("/admin/staff-invites/health", response_model=StaffInviteHealthResponse)
def staff_invite_health(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _staff_invite_health_response(repository.list_staff_invites())


@app.get(
    "/admin/staff-invites/delivery-readiness",
    response_model=StaffInviteDeliveryReadinessResponse,
)
def staff_invite_delivery_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _staff_invite_delivery_readiness_response(repository)


@app.get(
    "/admin/staff-invites/delivery-adapter-readiness",
    response_model=StaffInviteDeliveryAdapterReadinessResponse,
)
def staff_invite_delivery_adapter_readiness(
    _user: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    return _staff_invite_delivery_adapter_readiness_response()


@app.get(
    "/admin/staff-invites/delivery-outbox",
    response_model=StaffInviteDeliveryOutboxResponse,
)
def staff_invite_delivery_outbox(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _staff_invite_delivery_outbox_response(repository)


@app.post(
    "/admin/staff-invites/delivery-outbox/run",
    response_model=StaffInviteDeliveryOutboxRunResponse,
)
def run_staff_invite_delivery_outbox(
    payload: StaffInviteDeliveryOutboxRunCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _run_staff_invite_delivery_outbox(
        repository,
        payload=payload,
        actor_email=user["email"],
    )


@app.post(
    "/webhooks/staff-invite-delivery",
    response_model=StaffInviteDeliveryWebhookEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_staff_invite_delivery_webhook(
    payload: StaffInviteDeliveryWebhookCreate,
    request: Request,
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    raw_body = await request.body()
    _verify_staff_invite_delivery_webhook_signature(
        raw_body=raw_body,
        signature_header=request.headers.get(INVITE_DELIVERY_WEBHOOK_SIGNATURE_HEADER),
        timestamp_header=request.headers.get(INVITE_DELIVERY_WEBHOOK_TIMESTAMP_HEADER),
    )
    return _record_staff_invite_delivery_webhook_event(
        repository,
        payload=payload,
    )


@app.post(
    "/admin/staff-invites",
    response_model=StaffInviteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_staff_invite(
    payload: StaffInviteCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    email = payload.email.strip().lower()
    if repository.get_organization(payload.organization_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select a valid MFI organization",
        )
    if repository.get_user(email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )
    if _active_pending_staff_invite_for_email(repository, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active staff invite already exists",
        )

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    ).isoformat()
    raw_token = create_token()
    token_id = _staff_invite_token_id(raw_token)
    created = repository.create_staff_invite(
        token=token_id,
        email=email,
        role=payload.role,
        organization_id=payload.organization_id,
        created_by=user["email"],
        expires_at=expires_at,
    )
    _record_staff_invite_created(
        repository,
        actor_email=user["email"],
        token_id=token_id,
        email=email,
        role=payload.role,
        organization_id=payload.organization_id,
        expires_at=expires_at,
    )
    delivery_attempt = None
    response_invite = created
    if payload.queue_delivery:
        delivery_attempt, response_invite = _record_staff_invite_delivery_attempt(
            repository,
            invite=created,
            actor_email=user["email"],
            channel=payload.delivery_channel,
            recipient=payload.delivery_recipient,
            note=payload.delivery_note,
            provider=payload.delivery_provider,
        )
    return _staff_invite_response(
        response_invite,
        raw_token=raw_token,
        invite_url=_build_staff_invite_url(raw_token),
        delivery_attempt=delivery_attempt,
    )


@app.post(
    "/admin/staff-invites/{token_id}/delivery",
    response_model=StaffInviteDeliveryResponse,
)
def mark_staff_invite_delivery(
    token_id: str,
    payload: StaffInviteDeliveryCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    invite = repository.get_staff_invite(token_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    if invite.get("accepted_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted staff invite delivery is already complete",
        )
    if invite.get("revoked_at"):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Revoked staff invite cannot be delivered",
        )
    if _parse_utc_datetime(invite["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Expired staff invite cannot be delivered",
        )

    delivery_attempt, delivered = _record_staff_invite_delivery_attempt(
        repository,
        invite=invite,
        actor_email=user["email"],
        channel=payload.channel,
        recipient=payload.recipient,
        note=payload.note,
        provider="manual_receipt",
    )
    return _staff_invite_response(delivered, delivery_attempt=delivery_attempt)


@app.get(
    "/admin/staff-invites/{token_id}/delivery-attempts",
    response_model=list[StaffInviteDeliveryAttemptResponse],
)
def list_staff_invite_delivery_attempts(
    token_id: str,
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    if repository.get_staff_invite(token_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    return [
        _staff_invite_delivery_attempt_response(attempt)
        for attempt in repository.list_staff_invite_delivery_attempts(token_id)
    ]


@app.get(
    "/admin/staff-invites/{token_id}/delivery-events",
    response_model=list[StaffInviteDeliveryWebhookEventResponse],
)
def list_staff_invite_delivery_events(
    token_id: str,
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    if repository.get_staff_invite(token_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    return [
        _staff_invite_delivery_webhook_event_response(event)
        for event in repository.list_staff_invite_delivery_events(token_id)
    ]


@app.post(
    "/admin/staff-invites/{token_id}/delivery-attempts/retry",
    response_model=StaffInviteDeliveryResponse,
)
def retry_staff_invite_delivery(
    token_id: str,
    payload: StaffInviteDeliveryRetryCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    invite = repository.get_staff_invite(token_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    if invite.get("accepted_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted staff invite delivery is already complete",
        )
    if invite.get("revoked_at"):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Revoked staff invite cannot be delivered",
        )
    if _parse_utc_datetime(invite["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Expired staff invite cannot be delivered",
        )

    delivery_attempt, response_invite = _record_staff_invite_delivery_attempt(
        repository,
        invite=invite,
        actor_email=user["email"],
        channel=payload.channel,
        recipient=payload.recipient,
        note=payload.note,
        provider=payload.provider,
    )
    return _staff_invite_response(response_invite, delivery_attempt=delivery_attempt)


@app.post(
    "/admin/staff-invites/{token_id}/rotate",
    response_model=StaffInviteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def rotate_staff_invite(
    token_id: str,
    payload: StaffInviteRotateCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    invite = repository.get_staff_invite(token_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    if invite.get("accepted_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted staff invite cannot be rotated",
        )
    if repository.get_user(invite["email"]) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )
    if repository.get_organization(invite["organization_id"]) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select a valid MFI organization",
        )
    if _active_pending_staff_invite_for_email(
        repository,
        invite["email"],
        exclude_token_id=token_id,
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active staff invite already exists",
        )

    previous_status = _staff_invite_status_value(invite)
    if not invite.get("revoked_at"):
        repository.mark_staff_invite_revoked(token_id, user["email"])

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    ).isoformat()
    raw_token = create_token()
    rotated_token_id = _staff_invite_token_id(raw_token)
    created = repository.create_staff_invite(
        token=rotated_token_id,
        email=invite["email"],
        role=invite["role"],
        organization_id=invite["organization_id"],
        created_by=user["email"],
        expires_at=expires_at,
    )
    _record_staff_invite_created(
        repository,
        actor_email=user["email"],
        token_id=rotated_token_id,
        email=invite["email"],
        role=invite["role"],
        organization_id=invite["organization_id"],
        expires_at=expires_at,
        source="staff_invite_rotation",
    )
    repository.record_audit_event(
        actor_email=user["email"],
        action="staff_invite_rotated",
        entity_type="staff_invite",
        entity_id=rotated_token_id,
        details={
            "email": invite["email"],
            "role": invite["role"],
            "organization_id": invite["organization_id"],
            "previous_status": previous_status,
            "previous_token_preview": _staff_invite_token_preview(token_id),
            "new_token_preview": _staff_invite_token_preview(rotated_token_id),
            "expires_at": expires_at,
        },
    )
    delivery_attempt = None
    response_invite = created
    if payload.queue_delivery:
        delivery_attempt, response_invite = _record_staff_invite_delivery_attempt(
            repository,
            invite=created,
            actor_email=user["email"],
            channel=payload.delivery_channel,
            recipient=payload.delivery_recipient,
            note=payload.delivery_note,
            provider=payload.delivery_provider,
        )
    return _staff_invite_response(
        response_invite,
        raw_token=raw_token,
        invite_url=_build_staff_invite_url(raw_token),
        delivery_attempt=delivery_attempt,
    )


@app.delete("/admin/staff-invites/{token_id}", response_model=StaffInviteResponse)
def revoke_staff_invite(
    token_id: str,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    invite = repository.get_staff_invite(token_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff invite not found",
        )
    if invite.get("accepted_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted staff invite cannot be revoked",
        )
    if invite.get("revoked_at"):
        return _staff_invite_response(invite)

    revoked = repository.mark_staff_invite_revoked(token_id, user["email"])
    if not revoked:
        refreshed = repository.get_staff_invite(token_id)
        if refreshed and refreshed.get("revoked_at"):
            return _staff_invite_response(refreshed)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff invite can no longer be revoked",
        )

    updated = repository.get_staff_invite(token_id)
    repository.record_audit_event(
        actor_email=user["email"],
        action="staff_invite_revoked",
        entity_type="staff_invite",
        entity_id=token_id,
        details={
            "email": invite["email"],
            "role": invite["role"],
            "organization_id": invite["organization_id"],
            "token_preview": _staff_invite_token_preview(token_id),
        },
    )
    return _staff_invite_response(updated or invite)


@app.get("/admin/model-versions", response_model=list[ModelVersionPublic])
def list_admin_model_versions(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_model_versions()


@app.post(
    "/admin/model-versions",
    response_model=ModelVersionPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_model_version(
    payload: ModelVersionCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    try:
        created = repository.create_model_version(
            version=payload.version.strip(),
            model_name=payload.model_name,
            feature_schema_version=payload.feature_schema_version.strip(),
            training_data_label=payload.training_data_label.strip(),
            random_state=payload.random_state,
            metrics=dict(payload.metrics),
            limitations=[item.strip() for item in payload.limitations if item.strip()],
            created_by=user["email"],
        )
    except DuplicateModelVersionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model version already exists",
        )
    repository.record_audit_event(
        actor_email=user["email"],
        action="model_version_registered",
        entity_type="model_version",
        entity_id=created["version"],
        details={
            "model_name": created["model_name"],
            "feature_schema_version": created["feature_schema_version"],
            "training_data_label": created["training_data_label"],
            "random_state": created["random_state"],
        },
    )
    return created


@app.post(
    "/admin/model-versions/{version}/activate",
    response_model=ModelVersionPublic,
)
def activate_admin_model_version(
    version: str,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    previous = repository.get_active_model_version()
    activated = repository.activate_model_version(version)
    if activated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model version not found",
        )
    repository.record_audit_event(
        actor_email=user["email"],
        action="model_version_activated",
        entity_type="model_version",
        entity_id=version,
        details={
            "previous_active_version": (previous or {}).get("version"),
            "random_state": activated["random_state"],
        },
    )
    return activated


@app.post(
    "/admin/organizations",
    response_model=OrganizationPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_organization(
    payload: OrganizationCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    organization_id = payload.id.strip().lower()
    if not organization_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Organization id may contain letters, numbers, hyphens, and underscores",
        )
    try:
        created = repository.create_organization(
            organization_id=organization_id,
            name=payload.name.strip(),
            region=payload.region.strip(),
        )
    except DuplicateOrganizationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization already exists",
        )
    repository.record_audit_event(
        actor_email=user["email"],
        action="organization_created",
        entity_type="mfi_organization",
        entity_id=organization_id,
        details={"name": created["name"], "region": created["region"]},
    )
    return created


@app.post(
    "/admin/users",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_staff_user(
    payload: StaffUserCreate,
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    _validate_new_password(payload.password)
    email = payload.email.strip().lower()
    if repository.get_organization(payload.organization_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select a valid MFI organization",
        )
    try:
        created = repository.create_user(
            email,
            hash_password(payload.password),
            payload.role,
            payload.organization_id,
        )
    except DuplicateUserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    repository.record_audit_event(
        actor_email=user["email"],
        action="staff_user_created",
        entity_type="user",
        entity_id=email,
        details={
            "role": payload.role,
            "organization_id": payload.organization_id,
        },
    )
    return {
        "email": created["email"],
        "role": created["role"],
        "organization_id": created.get("organization_id"),
        "created_at": created["created_at"],
    }


@app.delete("/admin/applications", response_model=ClearApplicationsResponse)
def clear_applications(
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, int]:
    deleted_count = repository.clear_applications(actor_email=user["email"])
    return {"deleted_count": deleted_count}
