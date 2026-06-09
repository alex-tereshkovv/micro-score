r"""FastAPI prototype for MicroScore.

Install app dependencies with:

    .venv\Scripts\python -m pip install -e ".[app]"

Run locally with:

    .venv\Scripts\python -m uvicorn microscore_api.main:app --reload
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any
from uuid import uuid4

try:
    from fastapi import Depends, FastAPI, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional extra
    raise ModuleNotFoundError(
        'MicroScore API dependencies are missing. Install them with: pip install -e ".[app]"'
    ) from exc

from .database import DuplicateUserError, MicroScoreRepository
from .schemas import (
    ApplicationCreate,
    AuditEventResponse,
    AuthResponse,
    ClearApplicationsResponse,
    HealthResponse,
    LoanApplicationResponse,
    LoginRequest,
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


@app.get("/mfi/applications", response_model=list[LoanApplicationResponse])
def list_mfi_applications(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.list_applications()


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


@app.get("/mfi/analytics/segments", response_model=list[SegmentAnalyticsRow])
def segment_analytics(
    _user: dict[str, Any] = Depends(require_mfi_user),
    repository: MicroScoreRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return repository.segment_analytics()


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
