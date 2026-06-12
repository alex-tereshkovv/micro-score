r"""FastAPI prototype for MicroScore.

Install app dependencies with:

    .venv\Scripts\python -m pip install -e ".[app]"

Run locally with:

    .venv\Scripts\python -m uvicorn microscore_api.main:app --reload
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from functools import lru_cache
from io import StringIO
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

try:
    from fastapi import Depends, FastAPI, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional extra
    raise ModuleNotFoundError(
        'MicroScore API dependencies are missing. Install them with: pip install -e ".[app]"'
    ) from exc

from .database import DuplicateUserError, MicroScoreRepository
from .analytics import policy_analytics as build_policy_analytics
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
    PolicyAnalyticsResponse,
    RegisterRequest,
    SegmentAnalyticsRow,
    UserPublic,
)
from .scoring import get_scoring_service
from .security import create_token, hash_password, verify_password


app = FastAPI(
    title="MicroScore API",
    version="0.1.0",
    description="Prototype API for borrower applications, MFI review, and behavioral risk scoring.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
security = HTTPBearer()


@lru_cache(maxsize=1)
def get_repository() -> MicroScoreRepository:
    return MicroScoreRepository()


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


def _application_for_user(
    application_id: str,
    user: dict[str, Any],
    repository: MicroScoreRepository,
) -> dict[str, Any]:
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    is_owner = application["borrower_email"] == user["email"]
    can_review = user["role"] in {"mfi_analyst", "admin"}
    if not is_owner and not can_review:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return application


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@app.post("/auth/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    repository: MicroScoreRepository = Depends(get_repository),
) -> AuthResponse:
    email = payload.email.strip().lower()
    token = create_token()

    try:
        repository.create_user(email, hash_password(payload.password), payload.role)
    except DuplicateUserError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    repository.create_session(token, email)
    return AuthResponse(access_token=token, role=payload.role)


@app.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    repository: MicroScoreRepository = Depends(get_repository),
) -> AuthResponse:
    email = payload.email.strip().lower()
    user = repository.get_user(email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_token()
    repository.create_session(token, email)
    return AuthResponse(access_token=token, role=user["role"])


@app.get("/me", response_model=UserPublic)
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"email": user["email"], "role": user["role"], "created_at": user["created_at"]}


@app.post("/applications", response_model=LoanApplicationResponse)
def create_application(
    payload: ApplicationCreate,
    user: dict[str, Any] = Depends(current_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    if user["role"] != "borrower":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Borrower account required")

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
    )


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
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_applications()


@app.get("/mfi/applications/export.csv")
def export_mfi_applications(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> Response:
    csv_text = _portfolio_export_csv(repository.list_applications())
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
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

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
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
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
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    application = repository.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    timeline = [
        _timeline_event(event)
        for event in repository.list_application_timeline(application_id)
    ]
    return _review_packet(application, timeline)


@app.get("/mfi/analytics/segments", response_model=list[SegmentAnalyticsRow])
def segment_analytics(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.segment_analytics()


@app.get("/mfi/analytics/policies", response_model=PolicyAnalyticsResponse)
def policy_analytics(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return build_policy_analytics(repository.list_applications())


@app.get("/mfi/analytics/decisions", response_model=DecisionAnalyticsResponse)
def decision_analytics(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, Any]:
    return repository.decision_analytics()


@app.get("/admin/audit-events", response_model=list[AuditEventResponse])
def audit_events(
    _user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_audit_events()


@app.delete("/admin/applications", response_model=ClearApplicationsResponse)
def clear_applications(
    user: dict[str, Any] = Depends(require_admin_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> dict[str, int]:
    deleted_count = repository.clear_applications(actor_email=user["email"])
    return {"deleted_count": deleted_count}
