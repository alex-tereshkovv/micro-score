"""Request and response schemas for the MicroScore API prototype."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["borrower", "mfi_analyst", "admin"]
RiskBand = Literal["low", "medium", "high"]
ExplanationDirection = Literal["increases_risk", "reduces_risk"]
ApplicationDecision = Literal["approve", "review", "decline"]


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
    direction: ExplanationDirection | None = None
    label: str | None = None


class LocalExplanationResponse(BaseModel):
    method: str
    baseline_log_odds: float
    total_contribution: float
    predicted_log_odds: float
    high_risk_probability: float = Field(ge=0.0, le=1.0)
    top_positive_factors: list[ScoreFactor] = Field(default_factory=list)
    top_protective_factors: list[ScoreFactor] = Field(default_factory=list)
    top_factors: list[ScoreFactor] = Field(default_factory=list)


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
    explanation: LocalExplanationResponse | None = None
    top_model_factors: list[ScoreFactor] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApplicationDecisionCreate(BaseModel):
    decision: ApplicationDecision
    policy_name: str | None = None
    note: str = Field(default="", max_length=500)


class ApplicationDecisionResponse(BaseModel):
    id: int
    application_id: str
    actor_email: str
    decision: ApplicationDecision
    policy_name: str | None = None
    note: str
    created_at: str


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
    decision_result: ApplicationDecisionResponse | None = None
    created_at: str
    scored_at: str | None = None


class SegmentAnalyticsRow(BaseModel):
    segment_feature: str
    segment_value: str
    n: int = Field(ge=0)
    avg_high_risk_probability: float = Field(ge=0.0, le=1.0)
    high_risk_share: float = Field(ge=0.0, le=1.0)


class PolicyAnalyticsRow(BaseModel):
    policy: str
    description: str
    approve_threshold: float = Field(ge=0.0, le=1.0)
    decline_threshold: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=0)
    auto_approve_count: int = Field(ge=0)
    manual_review_count: int = Field(ge=0)
    auto_decline_count: int = Field(ge=0)
    auto_approval_rate: float = Field(ge=0.0, le=1.0)
    manual_review_rate: float = Field(ge=0.0, le=1.0)
    auto_decline_rate: float = Field(ge=0.0, le=1.0)
    mean_high_risk_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_approved_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_review_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_declined_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    predicted_high_risk_auto_approved_count: int = Field(ge=0)
    predicted_high_risk_auto_approval_rate: float = Field(ge=0.0, le=1.0)


class SegmentPolicyAnalyticsRow(BaseModel):
    policy: str
    segment_feature: str
    segment_value: str
    n: int = Field(ge=0)
    auto_approval_rate: float = Field(ge=0.0, le=1.0)
    manual_review_rate: float = Field(ge=0.0, le=1.0)
    auto_decline_rate: float = Field(ge=0.0, le=1.0)
    mean_high_risk_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    predicted_high_risk_share: float = Field(ge=0.0, le=1.0)


class PolicyAnalyticsResponse(BaseModel):
    scored_application_count: int = Field(ge=0)
    policies: list[PolicyAnalyticsRow] = Field(default_factory=list)
    segments: list[SegmentPolicyAnalyticsRow] = Field(default_factory=list)
    note: str


class DecisionAnalyticsRow(BaseModel):
    decision: ApplicationDecision
    count: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)


class DecisionPolicyAnalyticsRow(BaseModel):
    policy_name: str
    decision: ApplicationDecision
    count: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)


class DecisionRiskAnalyticsRow(BaseModel):
    risk_band: RiskBand
    decision: ApplicationDecision
    count: int = Field(ge=0)
    rate_within_risk_band: float = Field(ge=0.0, le=1.0)
    mean_high_risk_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class DecisionDistrictAnalyticsRow(BaseModel):
    district: str
    decision: ApplicationDecision
    count: int = Field(ge=0)
    rate_within_district: float = Field(ge=0.0, le=1.0)
    mean_high_risk_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class DecisionRecommendationAnalyticsRow(BaseModel):
    recommendation_code: str
    recommendation_title: str
    decision: ApplicationDecision
    count: int = Field(ge=0)
    rate_within_recommendation: float = Field(ge=0.0, le=1.0)
    mean_high_risk_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class DecisionProxyAnalyticsRow(BaseModel):
    proxy_sensitivity_bucket: str
    decision: ApplicationDecision
    count: int = Field(ge=0)
    rate_within_bucket: float = Field(ge=0.0, le=1.0)
    mean_high_risk_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_proxy_sensitivity_delta: float | None = Field(default=None, ge=0.0)


class DecisionAnalyticsResponse(BaseModel):
    application_count: int = Field(ge=0)
    decided_application_count: int = Field(ge=0)
    decision_rows: list[DecisionAnalyticsRow] = Field(default_factory=list)
    policy_rows: list[DecisionPolicyAnalyticsRow] = Field(default_factory=list)
    risk_rows: list[DecisionRiskAnalyticsRow] = Field(default_factory=list)
    district_rows: list[DecisionDistrictAnalyticsRow] = Field(default_factory=list)
    recommendation_rows: list[DecisionRecommendationAnalyticsRow] = Field(default_factory=list)
    proxy_rows: list[DecisionProxyAnalyticsRow] = Field(default_factory=list)
    note: str


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
