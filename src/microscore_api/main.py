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
from io import StringIO
import os
from typing import Any
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
    LoanApplicationResponse,
    LoginRequest,
    LogoutResponse,
    MeResponse,
    ModelStatusResponse,
    ModelVersionCreate,
    ModelVersionPublic,
    OrganizationCreate,
    OrganizationPublic,
    PilotReadinessResponse,
    PolicyAnalyticsResponse,
    PortfolioSimulationRequest,
    PortfolioSimulationResponse,
    PortfolioSimulationSummary,
    RegisterRequest,
    SegmentAnalyticsRow,
    StaffInviteAccept,
    StaffInviteCreate,
    StaffInviteCreatedResponse,
    StaffInviteResponse,
    StaffUserCreate,
    StaffUserDisableResponse,
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


def configured_cors_origins() -> list[str]:
    raw_value = os.environ.get("MICROSCORE_CORS_ORIGINS", "").strip()
    if not raw_value:
        return list(DEFAULT_CORS_ORIGINS)
    origins = [item.strip().rstrip("/") for item in raw_value.split(",")]
    return [origin for origin in origins if origin]


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


def _staff_invite_response(
    invite: dict[str, Any],
    *,
    raw_token: str | None = None,
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
    }
    if raw_token is not None:
        response["token"] = raw_token
    return response


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

    limiter.record_success(rate_key)
    token = create_token()
    session = repository.create_session(token, email)
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
    access_token = create_token()
    session = repository.create_session(access_token, email)
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


@app.get("/admin/users", response_model=list[UserPublic])
def list_admin_users(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_users()


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


@app.get("/admin/staff-invites", response_model=list[StaffInviteResponse])
def list_staff_invites(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [_staff_invite_response(invite) for invite in repository.list_staff_invites()]


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
    repository.record_audit_event(
        actor_email=user["email"],
        action="staff_invite_created",
        entity_type="staff_invite",
        entity_id=token_id,
        details={
            "email": email,
            "role": payload.role,
            "organization_id": payload.organization_id,
            "expires_at": expires_at,
            "token_preview": _staff_invite_token_preview(token_id),
        },
    )
    return _staff_invite_response(created, raw_token=raw_token)


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
