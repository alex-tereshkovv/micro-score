r"""FastAPI prototype for MicroScore.

Install app dependencies with:

    .venv\Scripts\python -m pip install -e ".[app]"

Run locally with:

    .venv\Scripts\python -m uvicorn microscore_api.main:app --reload
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac
import secrets
from typing import Any, Literal
from uuid import uuid4

try:
    from fastapi import Depends, FastAPI, HTTPException, status
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from pydantic import BaseModel, Field
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional extra
    raise ModuleNotFoundError(
        'MicroScore API dependencies are missing. Install them with: pip install -e ".[app]"'
    ) from exc

from .scoring import get_scoring_service

Role = Literal["borrower", "mfi_analyst", "admin"]


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: Role = "borrower"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


class ApplicationCreate(BaseModel):
    requested_amount: float = Field(gt=0)
    purpose: str = ""
    district: str | None = None
    settlement_type: str | None = None
    behavioral_signals: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(
    title="MicroScore API",
    version="0.1.0",
    description="Prototype API for borrower applications, MFI review, and behavioral risk scoring.",
)
security = HTTPBearer()

USERS: dict[str, dict[str, Any]] = {}
TOKENS: dict[str, str] = {}
APPLICATIONS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    salt, _digest = stored_hash.split("$", maxsplit=1)
    return secrets.compare_digest(_hash_password(password, salt), stored_hash)


def _create_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    TOKENS[token] = email
    return token


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    email = TOKENS.get(credentials.credentials)
    if email is None or email not in USERS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return USERS[email]


def require_mfi_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] not in {"mfi_analyst", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFI access required")
    return user


def _application_for_user(application_id: str, user: dict[str, Any]) -> dict[str, Any]:
    application = APPLICATIONS.get(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    is_owner = application["borrower_email"] == user["email"]
    can_review = user["role"] in {"mfi_analyst", "admin"}
    if not is_owner and not can_review:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return application


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "microscore-api"}


@app.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    email = payload.email.strip().lower()
    if email in USERS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    USERS[email] = {
        "email": email,
        "password_hash": _hash_password(payload.password),
        "role": payload.role,
        "created_at": _now_iso(),
    }
    return AuthResponse(access_token=_create_token(email), role=payload.role)


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    email = payload.email.strip().lower()
    user = USERS.get(email)
    if user is None or not _verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return AuthResponse(access_token=_create_token(email), role=user["role"])


@app.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"email": user["email"], "role": user["role"], "created_at": user["created_at"]}


@app.post("/applications")
def create_application(
    payload: ApplicationCreate,
    user: dict[str, Any] = Depends(current_user),
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

    APPLICATIONS[application_id] = {
        "id": application_id,
        "borrower_email": user["email"],
        "status": "submitted",
        "requested_amount": payload.requested_amount,
        "purpose": payload.purpose,
        "district": payload.district,
        "settlement_type": payload.settlement_type,
        "behavioral_signals": features,
        "score_result": None,
        "created_at": _now_iso(),
    }
    return APPLICATIONS[application_id]


@app.get("/applications/{application_id}")
def get_application(
    application_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return _application_for_user(application_id, user)


@app.get("/mfi/applications")
def list_mfi_applications(_user: dict[str, Any] = Depends(require_mfi_user)) -> list[dict[str, Any]]:
    return list(APPLICATIONS.values())


@app.post("/mfi/applications/{application_id}/score")
def score_application(
    application_id: str,
    _user: dict[str, Any] = Depends(require_mfi_user),
) -> dict[str, Any]:
    application = APPLICATIONS.get(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    score = get_scoring_service().score(application["behavioral_signals"])
    application["score_result"] = asdict(score)
    application["status"] = "scored"
    application["scored_at"] = _now_iso()
    return application


@app.get("/mfi/analytics/segments")
def segment_analytics(_user: dict[str, Any] = Depends(require_mfi_user)) -> list[dict[str, Any]]:
    scored = [item for item in APPLICATIONS.values() if item.get("score_result")]
    segments: dict[tuple[str, str], list[float]] = {}

    for item in scored:
        signals = item["behavioral_signals"]
        segment_values = {
            "settlement_type": item.get("settlement_type") or signals.get("settlement_type") or "unknown",
            "pavlodar_district": item.get("district") or signals.get("pavlodar_district") or "unknown",
            "gender": signals.get("gender") or "unknown",
            "employment_status": signals.get("employment_status") or "unknown",
        }
        for feature, value in segment_values.items():
            key = (feature, str(value))
            segments.setdefault(key, []).append(item["score_result"]["high_risk_probability"])

    rows: list[dict[str, Any]] = []
    for (feature, value), probabilities in sorted(segments.items()):
        rows.append(
            {
                "segment_feature": feature,
                "segment_value": value,
                "n": len(probabilities),
                "avg_high_risk_probability": sum(probabilities) / len(probabilities),
                "high_risk_share": sum(probability >= 0.65 for probability in probabilities)
                / len(probabilities),
            }
        )
    return rows
