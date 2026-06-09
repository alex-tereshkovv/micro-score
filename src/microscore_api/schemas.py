"""Request and response schemas for the MicroScore API prototype."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["borrower", "mfi_analyst", "admin"]
RiskBand = Literal["low", "medium", "high"]


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


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class UserPublic(BaseModel):
    email: str
    role: Role
    created_at: str


class ApplicationCreate(BaseModel):
    requested_amount: float = Field(gt=0)
    purpose: str = ""
    district: str | None = None
    settlement_type: str | None = None
    behavioral_signals: dict[str, Any] = Field(default_factory=dict)


class ScoreFactor(BaseModel):
    feature: str
    value: float
    abs_value: float


class ScenarioScoreResponse(BaseModel):
    scenario: str
    label: str
    high_risk_probability: float = Field(ge=0.0, le=1.0)
    risk_band: RiskBand
    notes: list[str] = Field(default_factory=list)


class DecisionSupportResponse(BaseModel):
    recommendation_code: str
    title: str
    rationale: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ScoreResultResponse(BaseModel):
    model_name: str
    model_version: str
    high_risk_probability: float = Field(ge=0.0, le=1.0)
    risk_band: RiskBand
    proxy_sensitivity_delta: float | None = Field(default=None, ge=0.0)
    scenario_scores: list[ScenarioScoreResponse] = Field(default_factory=list)
    decision_support: DecisionSupportResponse | None = None
    missing_feature_count: int = Field(default=0, ge=0)
    missing_features_preview: list[str] = Field(default_factory=list)
    top_model_factors: list[ScoreFactor] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LoanApplicationResponse(BaseModel):
    id: str
    borrower_email: str
    status: Literal["submitted", "scored"]
    requested_amount: float
    purpose: str
    district: str | None = None
    settlement_type: str | None = None
    behavioral_signals: dict[str, Any]
    score_result: ScoreResultResponse | None = None
    created_at: str
    scored_at: str | None = None


class SegmentAnalyticsRow(BaseModel):
    segment_feature: str
    segment_value: str
    n: int = Field(ge=0)
    avg_high_risk_probability: float = Field(ge=0.0, le=1.0)
    high_risk_share: float = Field(ge=0.0, le=1.0)


class AuditEventResponse(BaseModel):
    id: int
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    details: dict[str, Any]
    created_at: str


class ClearApplicationsResponse(BaseModel):
    deleted_count: int = Field(ge=0)
