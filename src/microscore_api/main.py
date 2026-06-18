r"""FastAPI prototype for MicroScore.

Install app dependencies with:

    .venv\Scripts\python -m pip install -e ".[app]"

Run locally with:

    .venv\Scripts\python -m uvicorn microscore_api.main:app --reload
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
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
    DuplicateOrganizationError,
    DuplicateUserError,
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
    ClearApplicationsResponse,
    DecisionAnalyticsResponse,
    HealthResponse,
    LoanApplicationResponse,
    LoginRequest,
    LogoutResponse,
    OrganizationCreate,
    OrganizationPublic,
    PilotReadinessResponse,
    PolicyAnalyticsResponse,
    RegisterRequest,
    SegmentAnalyticsRow,
    StaffUserCreate,
    UserPublic,
)
from .scoring import get_scoring_service
from .security import create_token, hash_password, password_policy_violations, verify_password


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

    forbidden_paths = find_forbidden_signal_paths(payload.behavioral_signals)
    if forbidden_paths:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Remove sensitive personal fields before submitting",
                "forbidden_fields": forbidden_paths,
            },
        )
    return consent_version


def _timeline_title(action: str) -> str:
    titles = {
        "application_created": "Application submitted",
        "application_scored": "Risk score generated",
        "application_decision_recorded": "Analyst decision recorded",
    }
    return titles.get(action, action.replace("_", " ").title())


def _timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "action": event["action"],
        "title": _timeline_title(event["action"]),
        "actor_email": event.get("actor_email"),
        "details": event.get("details") or {},
        "created_at": event["created_at"],
    }


def _review_packet(
    application: dict[str, Any],
    timeline_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    score = application.get("score_result")
    decision = application.get("decision_result")
    governance_flags = _review_governance_flags(application)

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
        "model_summary": _review_model_summary(score),
        "decision_support": (score or {}).get("decision_support") if score else None,
        "analyst_decision": decision,
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


def _review_model_summary(score: dict[str, Any] | None) -> dict[str, Any] | None:
    if not score:
        return None
    return {
        "model_name": score.get("model_name", "unknown"),
        "model_version": score.get("model_version", "unknown"),
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


def _review_governance_flags(application: dict[str, Any]) -> list[str]:
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

    repository.create_session(token, email)
    return AuthResponse(access_token=token, role=payload.role, organization_id=None)


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

    limiter.record_success(rate_key)
    token = create_token()
    repository.create_session(token, email)
    return AuthResponse(
        access_token=token,
        role=user["role"],
        organization_id=user.get("organization_id"),
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


@app.get("/me", response_model=UserPublic)
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {
        "email": user["email"],
        "role": user["role"],
        "organization_id": user.get("organization_id"),
        "created_at": user["created_at"],
    }


@app.post("/applications", response_model=LoanApplicationResponse)
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
    features = dict(payload.behavioral_signals)
    features["loan_application_amount"] = payload.requested_amount
    if payload.district:
        features["pavlodar_district"] = payload.district
    if payload.settlement_type:
        features["settlement_type"] = payload.settlement_type

    return repository.create_application(
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


@app.get("/applications", response_model=list[LoanApplicationResponse])
def list_borrower_applications(
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    if user["role"] != "borrower":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Borrower account required",
        )
    return repository.list_borrower_applications(user["email"])


@app.get("/applications/{application_id}", response_model=LoanApplicationResponse)
def get_application(
    application_id: str,
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _application_for_user(application_id, user, repository)


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
    return [
        _timeline_event(event)
        for event in repository.list_application_timeline(application_id)
    ]


@app.get("/mfi/applications", response_model=list[LoanApplicationResponse])
def list_mfi_applications(
    user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_applications(_mfi_organization_scope(user))


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

    score = get_scoring_service().score(application["behavioral_signals"])
    updated = repository.update_application_score(
        application_id=application_id,
        score_result=asdict(score),
        actor_email=user["email"],
    )
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

    updated = repository.record_application_decision(
        application_id=application_id,
        actor_email=user["email"],
        decision=payload.decision,
        policy_name=payload.policy_name,
        note=payload.note.strip(),
    )
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
    return _review_packet(application, timeline)


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
