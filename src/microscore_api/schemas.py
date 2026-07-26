"""Request and response schemas for the MicroScore API prototype."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .privacy import find_forbidden_signal_paths

Role = Literal["borrower", "mfi_analyst", "admin"]
RiskBand = Literal["low", "medium", "high"]
ExplanationDirection = Literal["increases_risk", "reduces_risk"]
ApplicationDecision = Literal["approve", "review", "decline"]
ReviewChecklistStatus = Literal["required", "suggested", "complete"]
ModelLifecycleStatus = Literal["candidate", "active", "inactive"]
ThresholdPolicyName = Literal[
    "lender_protective",
    "balanced_review",
    "inclusion_first",
    "starter_loan_review",
]
StressScenario = Literal["baseline", "adverse", "severe"]
ApplicationLifecycleStatus = Literal[
    "submitted",
    "scored",
    "under_review",
    "approved",
    "declined",
]
LifecycleScoringAction = Literal["score", "rescore"]
PavlodarDistrict = Literal[
    "Pavlodar city",
    "Ekibastuz",
    "Aksu",
    "Pavlodar district",
    "Bayanaul",
    "Sharbakty",
    "Terenkol",
    "Irtysh",
    "Zhelezinka",
    "Aktogay",
    "Akkuly",
    "Uspenka",
    "May district",
]
SettlementType = Literal["urban", "industrial_city", "peri_urban", "rural"]

DISTRICT_SETTLEMENT_TYPES: dict[str, SettlementType] = {
    "Pavlodar city": "urban",
    "Ekibastuz": "industrial_city",
    "Aksu": "industrial_city",
    "Pavlodar district": "peri_urban",
    "Bayanaul": "rural",
    "Sharbakty": "rural",
    "Terenkol": "rural",
    "Irtysh": "rural",
    "Zhelezinka": "rural",
    "Aktogay": "rural",
    "Akkuly": "rural",
    "Uspenka": "rural",
    "May district": "rural",
}


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)
    role: Role = "borrower"


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    organization_id: str | None = None
    session_expires_at: str
    session_ttl_seconds: int = Field(ge=1)


class LogoutResponse(BaseModel):
    revoked: bool


class StorageCapabilityResponse(BaseModel):
    id: str
    status: Literal["ready", "planned", "blocked"]
    detail: str


class StorageReadinessResponse(BaseModel):
    backend: Literal["sqlite"]
    status: Literal["ready"]
    production_ready: bool
    database_path: str
    database_exists: bool
    required_tables: list[str]
    json_columns: list[str]
    tenant_scoped_tables: list[str]
    capabilities: list[StorageCapabilityResponse]
    postgresql_migration_status: Literal["planned"]
    postgresql_migration_checklist: list[str]
    limitation: str


class PostgresSchemaTableResponse(BaseModel):
    table: str
    present_in_sqlite: bool
    column_count: int = Field(ge=0)
    primary_key_columns: list[str] = Field(default_factory=list)
    json_columns: list[str] = Field(default_factory=list)
    tenant_scope_columns: list[str] = Field(default_factory=list)
    migration_notes: list[str] = Field(default_factory=list)


class PostgresParityCheckResponse(BaseModel):
    key: str
    status: Literal["pass", "planned", "blocker"]
    sqlite_evidence: str
    postgres_requirement: str
    action: str


class PostgresMigrationControlResponse(BaseModel):
    key: str
    severity: Literal["blocker", "warning"]
    summary: str
    action: str


class PostgresMigrationReadinessResponse(BaseModel):
    status: Literal["ready", "planned", "blocked"]
    generated_at: str
    runtime_backend: Literal["sqlite"]
    target_backend: Literal["postgresql"]
    repository_backend_status: Literal["not_implemented", "implemented"]
    migration_ready: bool = False
    production_ready: bool = False
    live_connection_tested: bool = False
    required_environment: list[str] = Field(default_factory=list)
    configured_environment: list[str] = Field(default_factory=list)
    missing_environment: list[str] = Field(default_factory=list)
    required_table_count: int = Field(ge=0)
    present_table_count: int = Field(ge=0)
    json_column_count: int = Field(ge=0)
    tenant_scope_count: int = Field(ge=0)
    schema_inventory: list[PostgresSchemaTableResponse] = Field(default_factory=list)
    parity_checks: list[PostgresParityCheckResponse] = Field(default_factory=list)
    blockers: list[PostgresMigrationControlResponse] = Field(default_factory=list)
    next_required_controls: list[PostgresMigrationControlResponse] = Field(default_factory=list)
    limitation: str


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str
    storage: StorageReadinessResponse


class UserPublic(BaseModel):
    email: str
    role: Role
    organization_id: str | None = None
    created_at: str
    disabled_at: str | None = None
    disabled_by: str | None = None
    mfa_attested_at: str | None = None
    mfa_attested_by: str | None = None
    mfa_method: str | None = None


class MeResponse(UserPublic):
    session_expires_at: str
    session_ttl_seconds: int = Field(ge=1)


class StaffUserCreate(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)
    role: Literal["mfi_analyst"] = "mfi_analyst"
    organization_id: str = Field(min_length=1, max_length=100)


class StaffUserDisableResponse(UserPublic):
    revoked_session_count: int = Field(ge=0)
    was_already_disabled: bool = False


class StaffUserReactivateResponse(UserPublic):
    was_already_active: bool = False


class StaffSessionResponse(BaseModel):
    session_id: str
    session_preview: str
    email: str
    role: Literal["admin", "mfi_analyst"]
    organization_id: str | None = None
    session_created_at: str
    session_expires_at: str
    session_ttl_seconds: int = Field(ge=1)
    is_current_session: bool = False


class StaffSessionRevokeResponse(BaseModel):
    revoked: bool
    session_id: str
    email: str
    role: Literal["admin", "mfi_analyst"]
    organization_id: str | None = None


class MfaAttestationCreate(BaseModel):
    method: Literal[
        "pilot_attestation",
        "prototype_mfa_code",
        "totp",
        "webauthn",
        "external_idp",
    ] = "pilot_attestation"


class MfaAttestationResponse(UserPublic):
    was_already_attested: bool = False


class MfaReadinessAccount(BaseModel):
    email: str
    role: Role
    organization_id: str | None = None
    disabled: bool = False
    mfa_required: bool
    mfa_attested: bool
    mfa_attested_at: str | None = None
    mfa_method: str | None = None
    status: Literal["ready", "missing", "disabled"]


class MfaReadinessResponse(BaseModel):
    status: Literal["ready", "blocked"]
    active_staff_count: int = Field(ge=0)
    mfa_attested_count: int = Field(ge=0)
    missing_mfa_count: int = Field(ge=0)
    disabled_staff_count: int = Field(ge=0)
    accounts: list[MfaReadinessAccount] = Field(default_factory=list)
    recommended_action: str
    limitation: str


class SecurityReadinessCheck(BaseModel):
    key: str
    label: str
    status: Literal["pass", "warning", "blocker"]
    summary: str
    action: str


class SecurityReadinessResponse(BaseModel):
    status: Literal["ready", "review", "blocked"]
    generated_at: str
    blockers_count: int = Field(ge=0)
    warnings_count: int = Field(ge=0)
    checks: list[SecurityReadinessCheck] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    limitation: str


class IdentityReadinessComponent(BaseModel):
    key: str
    label: str
    status: Literal["pass", "warning", "blocker"]
    severity: Literal["info", "warning", "blocker"]
    summary: str
    action: str


class IdentityReadinessControl(BaseModel):
    key: str
    severity: Literal["blocker", "warning"]
    summary: str
    action: str


class IdentityReadinessResponse(BaseModel):
    status: Literal["ready", "review", "blocked"]
    generated_at: str
    auth_provider_mode: str
    invite_delivery_mode: str
    mfa_mode: str
    session_control_mode: str
    rate_limit_mode: str
    storage_backend: str
    tenant_isolation_mode: str
    active_staff_count: int = Field(ge=0)
    active_staff_session_count: int = Field(ge=0)
    active_pending_invite_count: int = Field(ge=0)
    components: list[IdentityReadinessComponent] = Field(default_factory=list)
    production_blockers: list[IdentityReadinessControl] = Field(default_factory=list)
    next_required_controls: list[IdentityReadinessControl] = Field(default_factory=list)
    limitation: str


InviteDeliveryChannel = Literal["email", "secure_message", "manual_copy", "local_demo"]
InviteDeliveryAttemptStatus = Literal["queued", "sent", "failed"]
InviteDeliveryConfigurationStatus = Literal["not_required", "missing", "invalid", "ready"]
InviteDeliveryWebhookEventType = Literal["delivered", "bounced", "failed", "deferred"]
InviteDeliveryWorkerStatus = Literal["queued", "retry_scheduled", "completed", "dead_letter"]


class StaffInviteDeliveryOptions(BaseModel):
    queue_delivery: bool = False
    delivery_channel: InviteDeliveryChannel = "email"
    delivery_recipient: str | None = Field(default=None, max_length=200)
    delivery_note: str | None = Field(default=None, max_length=500)
    delivery_provider: str | None = Field(default=None, max_length=100)


class StaffInviteCreate(StaffInviteDeliveryOptions):
    email: str
    role: Literal["mfi_analyst"] = "mfi_analyst"
    organization_id: str = Field(min_length=1, max_length=100)
    expires_in_hours: int = Field(default=48, ge=1, le=168)


class StaffInviteRotateCreate(StaffInviteDeliveryOptions):
    expires_in_hours: int = Field(default=48, ge=1, le=168)


class StaffInviteAccept(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class StaffInviteDeliveryCreate(BaseModel):
    channel: InviteDeliveryChannel = "manual_copy"
    recipient: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class StaffInviteDeliveryRetryCreate(BaseModel):
    channel: InviteDeliveryChannel = "email"
    recipient: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=100)


class StaffInviteDeliveryOutboxRunCreate(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: int = Field(default=300, ge=1, le=86_400)
    dry_run: bool = False


class StaffInviteDeliveryWebhookCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    provider_event_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(min_length=1, max_length=100)
    event_type: InviteDeliveryWebhookEventType
    occurred_at: str | None = Field(default=None, max_length=100)
    recipient: str | None = Field(default=None, max_length=200)
    error: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_sensitive_metadata(self) -> "StaffInviteDeliveryWebhookCreate":
        forbidden_terms = ("token", "secret", "password", "authorization", "api_key")

        def walk(value: Any, path: str = "metadata") -> list[str]:
            violations: list[str] = []
            if isinstance(value, dict):
                for key, nested in value.items():
                    key_text = str(key).lower()
                    key_path = f"{path}.{key}"
                    if any(term in key_text for term in forbidden_terms):
                        violations.append(key_path)
                    violations.extend(walk(nested, key_path))
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    violations.extend(walk(nested, f"{path}[{index}]"))
            return violations

        violations = walk(self.metadata)
        if violations:
            raise ValueError(
                "Webhook metadata cannot include secret-bearing keys: "
                + ", ".join(violations)
            )
        return self


class StaffInviteResponse(BaseModel):
    token_id: str
    token_preview: str
    email: str
    role: Literal["mfi_analyst"]
    organization_id: str
    created_by: str | None = None
    created_at: str
    expires_at: str
    accepted_at: str | None = None
    accepted_by: str | None = None
    revoked_at: str | None = None
    revoked_by: str | None = None
    delivered_at: str | None = None
    delivered_by: str | None = None
    delivery_channel: InviteDeliveryChannel | None = None
    delivery_recipient: str | None = None
    delivery_url_base: str | None = None
    delivery_note: str | None = None
    delivery_attempt_count: int = Field(default=0, ge=0)
    last_delivery_attempt_at: str | None = None
    last_delivery_status: InviteDeliveryAttemptStatus | None = None
    last_delivery_provider: str | None = None
    delivery_event_count: int = Field(default=0, ge=0)
    last_delivery_event_at: str | None = None
    last_delivery_event_type: InviteDeliveryWebhookEventType | None = None


class StaffInviteDeliveryAttemptResponse(BaseModel):
    attempt_id: str
    invite_token_id: str
    attempted_at: str
    attempted_by: str | None = None
    provider: str
    status: InviteDeliveryAttemptStatus
    channel: InviteDeliveryChannel
    recipient: str | None = None
    delivery_url_base: str | None = None
    note: str | None = None
    error: str | None = None
    worker_status: InviteDeliveryWorkerStatus = "completed"
    worker_attempt_count: int = Field(default=0, ge=0)
    next_worker_run_at: str | None = None
    dead_letter_at: str | None = None
    last_worker_error: str | None = None


class StaffInviteDeliveryWebhookEventResponse(BaseModel):
    event_id: str
    provider_event_id: str
    attempt_id: str
    invite_token_id: str
    provider: str
    event_type: InviteDeliveryWebhookEventType
    mapped_attempt_status: InviteDeliveryAttemptStatus
    received_at: str
    occurred_at: str | None = None
    recipient: str | None = None
    error: str | None = None
    was_duplicate: bool = False
    delivery_recorded: bool = False


class StaffInviteDeliveryOutboxItemResponse(BaseModel):
    attempt_id: str
    invite_token_id: str
    token_preview: str
    email: str
    provider: str
    adapter_idempotency_key: str
    attempt_status: InviteDeliveryAttemptStatus
    worker_status: InviteDeliveryWorkerStatus
    worker_attempt_count: int = Field(ge=0)
    next_worker_run_at: str | None = None
    dead_letter_at: str | None = None
    last_worker_error: str | None = None
    due: bool = False
    invite_active_pending: bool = False
    last_delivery_event_type: InviteDeliveryWebhookEventType | None = None


class StaffInviteDeliveryOutboxResponse(BaseModel):
    status: Literal["ok", "attention"]
    generated_at: str
    queued_count: int = Field(ge=0)
    due_count: int = Field(ge=0)
    retry_scheduled_count: int = Field(ge=0)
    dead_letter_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    items: list[StaffInviteDeliveryOutboxItemResponse] = Field(default_factory=list)
    recommended_action: str
    limitation: str


class StaffInviteDeliveryOutboxRunItemResponse(BaseModel):
    attempt_id: str
    invite_token_id: str
    provider: str
    adapter_idempotency_key: str
    action: Literal["scheduled_retry", "dead_lettered", "completed", "skipped", "dry_run"]
    previous_worker_status: InviteDeliveryWorkerStatus
    worker_status: InviteDeliveryWorkerStatus
    worker_attempt_count: int = Field(ge=0)
    next_worker_run_at: str | None = None
    dead_letter_at: str | None = None
    error: str | None = None


class StaffInviteDeliveryOutboxRunResponse(BaseModel):
    generated_at: str
    dry_run: bool
    processed_count: int = Field(ge=0)
    retry_scheduled_count: int = Field(ge=0)
    dead_lettered_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    results: list[StaffInviteDeliveryOutboxRunItemResponse] = Field(default_factory=list)
    limitation: str


class StaffInviteDeliveryProviderProfile(BaseModel):
    provider: str
    attempt_status: InviteDeliveryAttemptStatus
    mode: str
    configured: bool = False
    production_ready: bool = False
    configuration_status: InviteDeliveryConfigurationStatus = "not_required"
    configuration_ready: bool = False
    sends_message: bool = False
    audit_only: bool = True
    requires_https_invite_url: bool = True
    requires_external_secret: bool = False
    required_environment: list[str] = Field(default_factory=list)
    configured_environment: list[str] = Field(default_factory=list)
    missing_environment: list[str] = Field(default_factory=list)
    configuration_warnings: list[str] = Field(default_factory=list)
    summary: str
    action: str
    error: str | None = None


class StaffInviteDeliveryAdapterReadinessResponse(BaseModel):
    status: Literal["ready", "blocked"]
    generated_at: str
    provider: str
    adapter_mode: str
    send_adapter_ready: bool = False
    external_send_enabled: bool = False
    configuration_status: InviteDeliveryConfigurationStatus
    configuration_ready: bool = False
    secret_rotation_ready: bool = False
    idempotency_key_strategy: str
    safe_payload_fields: list[str] = Field(default_factory=list)
    forbidden_payload_fields: list[str] = Field(default_factory=list)
    webhook_correlation_fields: list[str] = Field(default_factory=list)
    required_environment: list[str] = Field(default_factory=list)
    optional_environment: list[str] = Field(default_factory=list)
    configured_environment: list[str] = Field(default_factory=list)
    missing_environment: list[str] = Field(default_factory=list)
    blockers: list[IdentityReadinessControl] = Field(default_factory=list)
    warnings: list[IdentityReadinessControl] = Field(default_factory=list)
    next_required_controls: list[IdentityReadinessControl] = Field(default_factory=list)
    limitation: str


class StaffInviteDeliveryReadinessResponse(BaseModel):
    status: Literal["ready", "review", "blocked"]
    generated_at: str
    configured_provider: str
    default_provider: str
    invite_url_base: str
    invite_url_https: bool
    invite_url_local: bool
    active_pending_invite_count: int = Field(ge=0)
    undelivered_active_invite_count: int = Field(ge=0)
    failed_latest_attempt_count: int = Field(ge=0)
    providers: list[StaffInviteDeliveryProviderProfile] = Field(default_factory=list)
    production_blockers: list[IdentityReadinessControl] = Field(default_factory=list)
    warnings: list[IdentityReadinessControl] = Field(default_factory=list)
    next_required_controls: list[IdentityReadinessControl] = Field(default_factory=list)
    limitation: str


class StaffInviteCreatedResponse(StaffInviteResponse):
    token: str
    invite_url: str
    delivery_attempt: StaffInviteDeliveryAttemptResponse | None = None


class StaffInviteDeliveryResponse(StaffInviteResponse):
    was_already_delivered: bool = False
    delivery_attempt: StaffInviteDeliveryAttemptResponse | None = None


class StaffInviteHealthResponse(BaseModel):
    status: Literal["ok", "attention"]
    total_count: int = Field(ge=0)
    active_pending_count: int = Field(ge=0)
    expiring_soon_count: int = Field(ge=0)
    expired_pending_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    revoked_count: int = Field(ge=0)
    action_required_count: int = Field(ge=0)
    window_hours: int = Field(ge=1)
    oldest_pending_created_at: str | None = None
    next_expiring_at: str | None = None
    recommended_action: str


class OrganizationCreate(BaseModel):
    id: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=200)
    region: str = Field(min_length=2, max_length=200)


class OrganizationPublic(BaseModel):
    id: str
    name: str
    region: str
    created_at: str


class ModelVersionCreate(BaseModel):
    version: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    model_name: Literal["Logistic Regression"] = "Logistic Regression"
    feature_schema_version: str = Field(min_length=2, max_length=100)
    training_data_label: str = Field(min_length=2, max_length=200)
    random_state: int = Field(default=42, ge=0, le=2_147_483_647)
    metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list, min_length=1, max_length=20)


class ModelVersionPublic(BaseModel):
    version: str
    model_name: str
    model_type: str
    lifecycle_status: ModelLifecycleStatus
    is_active: bool
    feature_schema_version: str
    training_data_label: str
    random_state: int
    metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    created_by: str | None = None
    created_at: str
    activated_at: str | None = None


class ModelStatusResponse(BaseModel):
    scoring_allowed: bool
    active_model: ModelVersionPublic | None = None
    note: str


class BehavioralSignalsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_income: float | None = Field(
        default=None, ge=0, le=10_000_000_000, allow_inf_nan=False
    )
    total_outstanding_debt: float | None = Field(
        default=None, ge=0, le=10_000_000_000, allow_inf_nan=False
    )
    mobile_banking_logins: int | None = Field(default=None, ge=0, le=10_000)
    online_transfer_frequency: int | None = Field(default=None, ge=0, le=10_000)
    atm_withdrawal_frequency: int | None = Field(default=None, ge=0, le=10_000)
    avg_deposit_amount: float | None = Field(
        default=None, ge=0, le=10_000_000_000, allow_inf_nan=False
    )
    debit_card_spending: float | None = Field(
        default=None, ge=0, le=10_000_000_000, allow_inf_nan=False
    )
    num_open_loans: int | None = Field(default=None, ge=0, le=100)
    late_payment_count: int | None = Field(default=None, ge=0, le=1_000)
    gender: Literal["Female", "Male", "Other"] | None = None
    employment_status: Literal["Self-employed", "Employed", "Unemployed"] | None = None


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    requested_amount: float = Field(ge=1_000, le=100_000_000, allow_inf_nan=False)
    purpose: str = Field(default="", max_length=200)
    district: PavlodarDistrict | None = None
    settlement_type: SettlementType | None = None
    organization_id: str = Field(min_length=1, max_length=100)
    consent_confirmed: bool = False
    consent_version: str | None = Field(default=None, max_length=64)
    behavioral_signals: BehavioralSignalsCreate = Field(default_factory=BehavioralSignalsCreate)

    @field_validator("behavioral_signals", mode="before")
    @classmethod
    def reject_sensitive_signal_fields(cls, value: Any) -> Any:
        forbidden_paths = find_forbidden_signal_paths(value or {})
        if forbidden_paths:
            raise ValueError(
                "Remove sensitive personal fields before submitting: "
                + ", ".join(forbidden_paths)
            )
        return value

    @model_validator(mode="after")
    def validate_district_settlement_pair(self) -> "ApplicationCreate":
        if self.district and self.settlement_type:
            expected = DISTRICT_SETTLEMENT_TYPES[self.district]
            if self.settlement_type != expected:
                raise ValueError(
                    f"Settlement type for {self.district} must be {expected}"
                )
        return self


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
    model_governance: dict[str, Any] = Field(default_factory=dict)
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


class ApplicationTimelineEventResponse(BaseModel):
    id: int
    action: str
    title: str
    actor_email: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class LoanApplicationResponse(BaseModel):
    id: str
    borrower_email: str
    status: ApplicationLifecycleStatus
    requested_amount: float
    purpose: str
    district: str | None = None
    settlement_type: str | None = None
    organization_id: str | None = None
    behavioral_signals: dict[str, Any]
    score_result: ScoreResultResponse | None = None
    decision_result: ApplicationDecisionResponse | None = None
    created_at: str
    scored_at: str | None = None


class BorrowerApplicationResponse(BaseModel):
    id: str
    status: ApplicationLifecycleStatus
    requested_amount: float
    purpose: str
    district: str | None = None
    settlement_type: str | None = None
    organization_id: str | None = None
    created_at: str
    scored_at: str | None = None
    status_message: str
    terminal: bool


class ReviewPacketApplicationSummary(BaseModel):
    id: str
    borrower_email: str
    status: str
    requested_amount: float
    purpose: str
    district: str | None = None
    settlement_type: str | None = None
    organization_id: str | None = None
    created_at: str
    scored_at: str | None = None


class ReviewPacketModelSummary(BaseModel):
    model_name: str
    model_version: str
    feature_schema_version: str | None = None
    training_data_label: str | None = None
    activated_at: str | None = None
    is_current_active: bool = True
    risk_band: RiskBand
    high_risk_probability: float = Field(ge=0.0, le=1.0)
    proxy_sensitivity_delta: float | None = Field(default=None, ge=0.0)
    missing_feature_count: int = Field(default=0, ge=0)


class ReviewChecklistItem(BaseModel):
    code: str
    title: str
    status: ReviewChecklistStatus
    evidence: str | None = None


class ApplicationLifecycleSummary(BaseModel):
    status: ApplicationLifecycleStatus
    terminal: bool
    scoring_action: LifecycleScoringAction | None = None
    allowed_decisions: list[ApplicationDecision] = Field(default_factory=list)
    status_note: str


class AffordabilitySnapshot(BaseModel):
    annual_income: float | None = Field(default=None, ge=0.0)
    total_outstanding_debt: float | None = Field(default=None, ge=0.0)
    num_open_loans: int | None = Field(default=None, ge=0)
    debt_to_income_ratio: float | None = Field(default=None, ge=0.0)
    requested_amount_to_income_ratio: float | None = Field(default=None, ge=0.0)
    completeness: float = Field(ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)
    note: str


class ApplicationReviewPacketResponse(BaseModel):
    application_id: str
    generated_at: str
    application: ReviewPacketApplicationSummary
    model_summary: ReviewPacketModelSummary | None = None
    decision_support: DecisionSupportResponse | None = None
    analyst_decision: ApplicationDecisionResponse | None = None
    decision_history: list[ApplicationDecisionResponse] = Field(default_factory=list)
    lifecycle: ApplicationLifecycleSummary
    affordability: AffordabilitySnapshot
    timeline_events: list[ApplicationTimelineEventResponse] = Field(default_factory=list)
    scenario_scores: list[ScenarioScoreResponse] = Field(default_factory=list)
    top_risk_factors: list[ScoreFactor] = Field(default_factory=list)
    top_protective_factors: list[ScoreFactor] = Field(default_factory=list)
    governance_flags: list[str] = Field(default_factory=list)
    checklist: list[ReviewChecklistItem] = Field(default_factory=list)
    audit_note: str


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


class PortfolioSimulationRequest(BaseModel):
    iterations: int = Field(default=5_000, ge=100, le=20_000)
    seed: int = Field(default=20_260_619, ge=0, le=4_294_967_295)
    policy: ThresholdPolicyName = "balanced_review"
    scenarios: list[StressScenario] = Field(
        default_factory=lambda: ["baseline", "adverse", "severe"],
        min_length=1,
        max_length=3,
    )
    review_approval_rate: float = Field(default=0.50, ge=0.0, le=1.0)
    interest_margin_rate: float = Field(default=0.22, ge=0.0, le=1.0)
    loss_given_default: float = Field(default=0.65, ge=0.0, le=1.0)
    operating_cost_per_approved: float = Field(default=0.0, ge=0.0)
    macro_volatility: float = Field(default=0.25, ge=0.0, le=2.0)
    calibration_volatility: float = Field(default=0.15, ge=0.0, le=2.0)


class SimulationDistribution(BaseModel):
    mean: float
    p05: float
    p50: float
    p95: float


class SimulationPolicySummary(BaseModel):
    name: ThresholdPolicyName
    description: str
    approve_threshold: float = Field(ge=0.0, le=1.0)
    decline_threshold: float = Field(ge=0.0, le=1.0)
    auto_approve_count: int = Field(ge=0)
    manual_review_count: int = Field(ge=0)
    auto_decline_count: int = Field(ge=0)


class SimulationAssumptions(BaseModel):
    iterations: int = Field(ge=1)
    seed: int = Field(ge=0)
    review_approval_rate: float = Field(ge=0.0, le=1.0)
    interest_margin_rate: float = Field(ge=0.0, le=1.0)
    loss_given_default: float = Field(ge=0.0, le=1.0)
    operating_cost_per_approved: float = Field(ge=0.0)
    macro_volatility: float = Field(ge=0.0)
    calibration_volatility: float = Field(ge=0.0)
    scenario_log_odds_shifts: dict[str, float] = Field(default_factory=dict)
    borrower_iterations: int = Field(ge=1)


class SimulationDiagnostics(BaseModel):
    portfolio_result_mean_standard_error: float = Field(ge=0.0)
    default_count_mean_standard_error: float = Field(ge=0.0)
    loss_probability_standard_error: float = Field(ge=0.0)


class PortfolioSimulationScenario(BaseModel):
    scenario: StressScenario
    log_odds_shift: float
    approved_count: SimulationDistribution
    default_count: SimulationDistribution
    default_rate: SimulationDistribution
    approved_exposure: SimulationDistribution
    portfolio_result: SimulationDistribution
    result_per_approved: SimulationDistribution
    mean_stressed_probability: float = Field(ge=0.0, le=1.0)
    probability_of_loss: float = Field(ge=0.0, le=1.0)
    downside_p05: float
    diagnostics: SimulationDiagnostics


class PortfolioSimulationResponse(BaseModel):
    simulation_id: str
    generated_at: str
    organization_id: str | None = None
    actor_email: str | None = None
    application_count: int = Field(ge=0)
    scored_application_count: int = Field(ge=0)
    unscored_application_count: int = Field(ge=0)
    model_versions: list[str] = Field(default_factory=list)
    portfolio_fingerprint: str = Field(min_length=64, max_length=64)
    policy: SimulationPolicySummary
    assumptions: SimulationAssumptions
    scenarios: list[PortfolioSimulationScenario] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    note: str


class PortfolioSimulationScenarioSummary(BaseModel):
    scenario: StressScenario
    probability_of_loss: float = Field(ge=0.0, le=1.0)
    portfolio_result_p50: float


class PortfolioSimulationSummary(BaseModel):
    simulation_id: str
    generated_at: str
    organization_id: str | None = None
    actor_email: str
    portfolio_fingerprint: str = Field(min_length=64, max_length=64)
    policy: ThresholdPolicyName
    iterations: int = Field(ge=1)
    seed: int = Field(ge=0)
    scenarios: list[StressScenario] = Field(default_factory=list)
    scored_application_count: int = Field(ge=0)
    model_versions: list[str] = Field(default_factory=list)
    warning_count: int = Field(ge=0)
    scenario_summary: list[PortfolioSimulationScenarioSummary] = Field(default_factory=list)


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


class PilotDataClassRow(BaseModel):
    data_class: str
    collect_in_pilot: str
    model_use: str
    notes: str


class PilotReadinessResponse(BaseModel):
    status: str
    region: str
    privacy_note: str
    data_classes: list[PilotDataClassRow] = Field(default_factory=list)
    forbidden_data: list[str] = Field(default_factory=list)
    validation_questions: list[str] = Field(default_factory=list)
    first_pilot_success_criteria: list[str] = Field(default_factory=list)


class PrePilotReadinessCheck(BaseModel):
    key: str
    label: str
    category: Literal[
        "security",
        "identity",
        "delivery",
        "storage",
        "model",
        "simulation",
        "privacy",
        "tenant",
        "demo",
    ]
    status: Literal["pass", "warning", "blocker"]
    summary: str
    action: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class PrePilotReadinessResponse(BaseModel):
    status: Literal["ready", "review", "blocked"]
    generated_at: str
    region: str
    release_target: str
    blockers_count: int = Field(ge=0)
    warnings_count: int = Field(ge=0)
    passes_count: int = Field(ge=0)
    readiness_score: int = Field(ge=0, le=100)
    production_data_allowed: bool = False
    public_demo_allowed: bool = False
    checks: list[PrePilotReadinessCheck] = Field(default_factory=list)
    next_required_controls: list[IdentityReadinessControl] = Field(default_factory=list)
    signed_off_capabilities: list[str] = Field(default_factory=list)
    blocked_capabilities: list[str] = Field(default_factory=list)
    limitation: str
