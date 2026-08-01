"""PostgreSQL repository adapter contract and completed method groups.

This module is deliberately not a production backend yet. It records the
repository method families that a future PostgreSQL implementation must support
before ``MICROSCORE_STORAGE_BACKEND=postgresql`` can be enabled, and it exposes
the first executable method groups for repository parity tests.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from typing import Any, NoReturn


POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION = "postgresql-repository-adapter-v8"
POSTGRESQL_REPOSITORY_ADAPTER_MODULE = "microscore_api.postgres_repository"
POSTGRESQL_REPOSITORY_ADAPTER_STATUS = "partial_method_groups"
POSTGRESQL_REPOSITORY_ADAPTER_STAGE = "model_registry_audit_organizations_identity_invites_applications_groups_v1"
DEFAULT_SESSION_TTL_HOURS = 8.0
STAFF_ROLES = {"admin", "mfi_analyst"}
DECISION_VALUES = ("approve", "review", "decline")
DECISION_WORKFLOW_STATUSES = {
    "approve": "approved",
    "review": "under_review",
    "decline": "declined",
}
TERMINAL_APPLICATION_STATUSES = {"approved", "declined"}
DECISION_TRANSITIONS = {
    "scored": {"approve", "review", "decline"},
    "under_review": {"approve", "decline"},
}
POSTGRESQL_MODEL_REGISTRY_READ_METHODS = (
    "get_model_version",
    "get_active_model_version",
    "list_model_versions",
)
POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS = (
    "create_model_version",
    "activate_model_version",
)
POSTGRESQL_MODEL_REGISTRY_METHODS = (
    "create_model_version",
    "get_model_version",
    "get_active_model_version",
    "list_model_versions",
    "activate_model_version",
)
POSTGRESQL_AUDIT_READ_METHODS = ("list_audit_events",)
POSTGRESQL_AUDIT_WRITE_METHODS = ("record_audit_event",)
POSTGRESQL_AUDIT_METHODS = (
    "record_audit_event",
    "list_audit_events",
)
POSTGRESQL_ORGANIZATION_READ_METHODS = (
    "get_organization",
    "list_organizations",
)
POSTGRESQL_ORGANIZATION_WRITE_METHODS = (
    "create_organization",
    "assign_user_organization",
)
POSTGRESQL_ORGANIZATION_METHODS = (
    "create_organization",
    "get_organization",
    "list_organizations",
    "assign_user_organization",
)
POSTGRESQL_IDENTITY_READ_METHODS = (
    "get_user",
    "list_users",
    "get_user_by_token",
    "list_active_sessions",
)
POSTGRESQL_IDENTITY_WRITE_METHODS = (
    "create_user",
    "disable_user",
    "reactivate_user",
    "attest_user_mfa",
    "create_session",
    "revoke_session",
    "revoke_session_by_id",
)
POSTGRESQL_IDENTITY_METHODS = (
    "create_user",
    "get_user",
    "list_users",
    "disable_user",
    "reactivate_user",
    "attest_user_mfa",
    "create_session",
    "get_user_by_token",
    "list_active_sessions",
    "revoke_session",
    "revoke_session_by_id",
)
POSTGRESQL_STAFF_INVITE_READ_METHODS = (
    "get_staff_invite",
    "list_staff_invites",
    "get_staff_invite_delivery_attempt",
    "get_staff_invite_delivery_event",
    "list_staff_invite_delivery_attempts",
    "list_staff_invite_delivery_events",
    "list_staff_invite_delivery_outbox_attempts",
)
POSTGRESQL_STAFF_INVITE_WRITE_METHODS = (
    "create_staff_invite",
    "mark_staff_invite_accepted",
    "mark_staff_invite_revoked",
    "mark_staff_invite_delivered",
    "record_staff_invite_delivery_attempt",
    "record_staff_invite_delivery_event",
    "update_staff_invite_delivery_attempt_status",
    "update_staff_invite_delivery_worker_state",
)
POSTGRESQL_STAFF_INVITE_METHODS = (
    "create_staff_invite",
    "get_staff_invite",
    "list_staff_invites",
    "mark_staff_invite_accepted",
    "mark_staff_invite_revoked",
    "mark_staff_invite_delivered",
    "record_staff_invite_delivery_attempt",
    "record_staff_invite_delivery_event",
    "get_staff_invite_delivery_attempt",
    "get_staff_invite_delivery_event",
    "list_staff_invite_delivery_attempts",
    "list_staff_invite_delivery_events",
    "list_staff_invite_delivery_outbox_attempts",
    "update_staff_invite_delivery_attempt_status",
    "update_staff_invite_delivery_worker_state",
)
POSTGRESQL_APPLICATION_LIFECYCLE_READ_METHODS = (
    "get_application",
    "list_applications",
    "list_borrower_applications",
    "list_application_decisions",
    "list_application_timeline",
)
POSTGRESQL_APPLICATION_LIFECYCLE_WRITE_METHODS = (
    "create_application",
    "assign_application_organization",
    "update_application_score",
    "record_application_decision",
    "clear_applications",
)
POSTGRESQL_APPLICATION_LIFECYCLE_METHODS = (
    "create_application",
    "get_application",
    "list_applications",
    "list_borrower_applications",
    "assign_application_organization",
    "update_application_score",
    "record_application_decision",
    "list_application_decisions",
    "list_application_timeline",
    "clear_applications",
)
POSTGRESQL_REPOSITORY_IMPLEMENTED_METHODS = (
    *POSTGRESQL_MODEL_REGISTRY_METHODS,
    *POSTGRESQL_AUDIT_METHODS,
    *POSTGRESQL_ORGANIZATION_METHODS,
    *POSTGRESQL_IDENTITY_METHODS,
    *POSTGRESQL_STAFF_INVITE_METHODS,
    *POSTGRESQL_APPLICATION_LIFECYCLE_METHODS,
)
POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION = (
    "PostgreSQL Repository Adapter v8 implements the model registry, audit, "
    "organization, identity/session, staff invite delivery, and application "
    "lifecycle method groups through an injected DB-API compatible connection "
    "factory. Runtime backend selection remains disabled until tenant-scoped "
    "simulation and analytics flows have "
    "repository parity coverage."
)


class InvalidApplicationTransitionError(ValueError):
    """Raised when an application lifecycle transition is not allowed."""
USER_COLUMNS = (
    "email",
    "password_hash",
    "role",
    "organization_id",
    "created_at",
    "disabled_at",
    "disabled_by",
    "mfa_attested_at",
    "mfa_attested_by",
    "mfa_method",
)
LIST_USER_COLUMNS = (
    "email",
    "role",
    "organization_id",
    "created_at",
    "disabled_at",
    "disabled_by",
    "mfa_attested_at",
    "mfa_attested_by",
    "mfa_method",
)
SESSION_USER_COLUMNS = (
    *USER_COLUMNS,
    "session_created_at",
)
ACTIVE_SESSION_COLUMNS = (
    "token",
    "email",
    "session_created_at",
    "role",
    "organization_id",
    "disabled_at",
)
USER_SELECT = """
SELECT
    email,
    password_hash,
    role,
    organization_id,
    created_at,
    disabled_at,
    disabled_by,
    mfa_attested_at,
    mfa_attested_by,
    mfa_method
FROM users
"""
GET_USER_SQL = USER_SELECT + "WHERE email = %(email)s"
LIST_USERS_SQL = """
SELECT
    email,
    role,
    organization_id,
    created_at,
    disabled_at,
    disabled_by,
    mfa_attested_at,
    mfa_attested_by,
    mfa_method
FROM users
ORDER BY role, email
"""
CREATE_USER_SQL = """
INSERT INTO users (
    email,
    password_hash,
    role,
    organization_id,
    created_at
)
VALUES (
    %(email)s,
    %(password_hash)s,
    %(role)s,
    %(organization_id)s,
    %(created_at)s
)
"""
GET_USER_DISABLE_STATUS_SQL = """
SELECT email, disabled_at
FROM users
WHERE email = %(email)s
"""
DISABLE_USER_SQL = """
UPDATE users
SET disabled_at = %(disabled_at)s, disabled_by = %(disabled_by)s
WHERE email = %(email)s AND disabled_at IS NULL
"""
GET_USER_REACTIVATE_STATUS_SQL = """
SELECT email, disabled_at, disabled_by
FROM users
WHERE email = %(email)s
"""
REACTIVATE_USER_SQL = """
UPDATE users
SET disabled_at = NULL, disabled_by = NULL
WHERE email = %(email)s AND disabled_at IS NOT NULL
"""
GET_USER_MFA_STATUS_SQL = """
SELECT email, mfa_attested_at
FROM users
WHERE email = %(email)s
"""
ATTEST_USER_MFA_SQL = """
UPDATE users
SET
    mfa_attested_at = %(mfa_attested_at)s,
    mfa_attested_by = %(mfa_attested_by)s,
    mfa_method = %(mfa_method)s
WHERE email = %(email)s AND mfa_attested_at IS NULL
"""
CREATE_SESSION_SQL = """
INSERT INTO sessions (token, email, created_at)
VALUES (%(token)s, %(email)s, %(created_at)s)
"""
GET_USER_BY_TOKEN_SQL = """
SELECT
    users.email,
    users.password_hash,
    users.role,
    users.organization_id,
    users.created_at,
    users.disabled_at,
    users.disabled_by,
    users.mfa_attested_at,
    users.mfa_attested_by,
    users.mfa_method,
    sessions.created_at AS session_created_at
FROM sessions
JOIN users ON users.email = sessions.email
WHERE sessions.token = %(token)s
"""
DELETE_SESSION_BY_TOKEN_SQL = """
DELETE FROM sessions
WHERE token = %(token)s
"""
DELETE_SESSIONS_BY_EMAIL_SQL = """
DELETE FROM sessions
WHERE email = %(email)s
"""
LIST_ACTIVE_SESSIONS_SQL = """
SELECT
    sessions.token,
    sessions.email,
    sessions.created_at AS session_created_at,
    users.role,
    users.organization_id,
    users.disabled_at
FROM sessions
JOIN users ON users.email = sessions.email
ORDER BY sessions.created_at DESC
"""
ORGANIZATION_COLUMNS = (
    "id",
    "name",
    "region",
    "created_at",
)
ORGANIZATION_SELECT = """
SELECT
    id,
    name,
    region,
    created_at
FROM mfi_organizations
"""
GET_ORGANIZATION_SQL = ORGANIZATION_SELECT + "WHERE id = %(organization_id)s"
LIST_ORGANIZATIONS_SQL = (
    ORGANIZATION_SELECT
    + """
ORDER BY name
"""
)
CREATE_ORGANIZATION_SQL = """
INSERT INTO mfi_organizations (
    id,
    name,
    region,
    created_at
)
VALUES (
    %(organization_id)s,
    %(name)s,
    %(region)s,
    %(created_at)s
)
"""
ASSIGN_USER_ORGANIZATION_SQL = """
UPDATE users
SET organization_id = %(organization_id)s
WHERE email = %(email)s
"""
STAFF_INVITE_BASE_COLUMNS = (
    "token",
    "email",
    "role",
    "organization_id",
    "created_by",
    "created_at",
    "expires_at",
    "accepted_at",
    "accepted_by",
    "revoked_at",
    "revoked_by",
    "delivered_at",
    "delivered_by",
    "delivery_channel",
    "delivery_recipient",
    "delivery_url_base",
    "delivery_note",
)
STAFF_INVITE_COLUMNS = (
    *STAFF_INVITE_BASE_COLUMNS,
    "delivery_attempt_count",
    "last_delivery_attempt_at",
    "last_delivery_status",
    "last_delivery_provider",
    "delivery_event_count",
    "last_delivery_event_at",
    "last_delivery_event_type",
)
STAFF_INVITE_SELECT = """
SELECT
    token,
    email,
    role,
    organization_id,
    created_by,
    created_at,
    expires_at,
    accepted_at,
    accepted_by,
    revoked_at,
    revoked_by,
    delivered_at,
    delivered_by,
    delivery_channel,
    delivery_recipient,
    delivery_url_base,
    delivery_note,
    COALESCE((
        SELECT COUNT(*)
        FROM staff_invite_delivery_attempts
        WHERE invite_token = staff_invites.token
    ), 0) AS delivery_attempt_count,
    (
        SELECT attempted_at
        FROM staff_invite_delivery_attempts
        WHERE invite_token = staff_invites.token
        ORDER BY attempted_at DESC, attempt_id DESC
        LIMIT 1
    ) AS last_delivery_attempt_at,
    (
        SELECT status
        FROM staff_invite_delivery_attempts
        WHERE invite_token = staff_invites.token
        ORDER BY attempted_at DESC, attempt_id DESC
        LIMIT 1
    ) AS last_delivery_status,
    (
        SELECT provider
        FROM staff_invite_delivery_attempts
        WHERE invite_token = staff_invites.token
        ORDER BY attempted_at DESC, attempt_id DESC
        LIMIT 1
    ) AS last_delivery_provider,
    COALESCE((
        SELECT COUNT(*)
        FROM staff_invite_delivery_events
        WHERE invite_token = staff_invites.token
    ), 0) AS delivery_event_count,
    (
        SELECT received_at
        FROM staff_invite_delivery_events
        WHERE invite_token = staff_invites.token
        ORDER BY received_at DESC, event_id DESC
        LIMIT 1
    ) AS last_delivery_event_at,
    (
        SELECT event_type
        FROM staff_invite_delivery_events
        WHERE invite_token = staff_invites.token
        ORDER BY received_at DESC, event_id DESC
        LIMIT 1
    ) AS last_delivery_event_type
FROM staff_invites
"""
GET_STAFF_INVITE_SQL = STAFF_INVITE_SELECT + "WHERE token = %(token)s"
LIST_STAFF_INVITES_SQL = (
    STAFF_INVITE_SELECT
    + """
ORDER BY created_at DESC
"""
)
CREATE_STAFF_INVITE_SQL = """
INSERT INTO staff_invites (
    token,
    email,
    role,
    organization_id,
    created_by,
    created_at,
    expires_at
)
VALUES (
    %(token)s,
    %(email)s,
    %(role)s,
    %(organization_id)s,
    %(created_by)s,
    %(created_at)s,
    %(expires_at)s
)
"""
MARK_STAFF_INVITE_ACCEPTED_SQL = """
UPDATE staff_invites
SET accepted_at = %(accepted_at)s, accepted_by = %(accepted_by)s
WHERE token = %(token)s AND accepted_at IS NULL AND revoked_at IS NULL
"""
MARK_STAFF_INVITE_REVOKED_SQL = """
UPDATE staff_invites
SET revoked_at = %(revoked_at)s, revoked_by = %(revoked_by)s
WHERE token = %(token)s AND accepted_at IS NULL AND revoked_at IS NULL
"""
MARK_STAFF_INVITE_DELIVERED_SQL = """
UPDATE staff_invites
SET
    delivered_at = %(delivered_at)s,
    delivered_by = %(delivered_by)s,
    delivery_channel = %(channel)s,
    delivery_recipient = %(recipient)s,
    delivery_url_base = %(url_base)s,
    delivery_note = %(note)s
WHERE token = %(token)s AND delivered_at IS NULL
"""
STAFF_INVITE_DELIVERY_ATTEMPT_COLUMNS = (
    "attempt_id",
    "invite_token",
    "attempted_at",
    "attempted_by",
    "provider",
    "status",
    "channel",
    "recipient",
    "delivery_url_base",
    "note",
    "error",
    "worker_status",
    "worker_attempt_count",
    "next_worker_run_at",
    "dead_letter_at",
    "last_worker_error",
)
STAFF_INVITE_DELIVERY_ATTEMPT_SELECT = """
SELECT
    attempt_id,
    invite_token,
    attempted_at,
    attempted_by,
    provider,
    status,
    channel,
    recipient,
    delivery_url_base,
    note,
    error,
    worker_status,
    worker_attempt_count,
    next_worker_run_at,
    dead_letter_at,
    last_worker_error
FROM staff_invite_delivery_attempts
"""
GET_STAFF_INVITE_DELIVERY_ATTEMPT_SQL = (
    STAFF_INVITE_DELIVERY_ATTEMPT_SELECT
    + """
WHERE attempt_id = %(attempt_id)s
"""
)
LIST_STAFF_INVITE_DELIVERY_ATTEMPTS_SQL = (
    STAFF_INVITE_DELIVERY_ATTEMPT_SELECT
    + """
WHERE invite_token = %(token)s
ORDER BY attempted_at DESC, attempt_id DESC
"""
)
RECORD_STAFF_INVITE_DELIVERY_ATTEMPT_SQL = """
INSERT INTO staff_invite_delivery_attempts (
    attempt_id,
    invite_token,
    attempted_at,
    attempted_by,
    provider,
    status,
    channel,
    recipient,
    delivery_url_base,
    note,
    error,
    worker_status,
    worker_attempt_count,
    next_worker_run_at,
    dead_letter_at,
    last_worker_error
)
VALUES (
    %(attempt_id)s,
    %(token)s,
    %(attempted_at)s,
    %(attempted_by)s,
    %(provider)s,
    %(status)s,
    %(channel)s,
    %(recipient)s,
    %(url_base)s,
    %(note)s,
    %(error)s,
    %(worker_status)s,
    %(worker_attempt_count)s,
    %(next_worker_run_at)s,
    %(dead_letter_at)s,
    %(last_worker_error)s
)
"""
UPDATE_STAFF_INVITE_DELIVERY_ATTEMPT_STATUS_SQL = """
UPDATE staff_invite_delivery_attempts
SET
    status = %(status)s,
    error = %(error)s,
    worker_status = %(worker_status)s,
    next_worker_run_at = %(next_worker_run_at)s,
    dead_letter_at = %(dead_letter_at)s,
    last_worker_error = %(last_worker_error)s
WHERE attempt_id = %(attempt_id)s
"""
UPDATE_STAFF_INVITE_DELIVERY_WORKER_STATE_SQL = """
UPDATE staff_invite_delivery_attempts
SET
    status = %(status)s,
    error = %(error)s,
    worker_status = %(worker_status)s,
    worker_attempt_count = %(worker_attempt_count)s,
    next_worker_run_at = %(next_worker_run_at)s,
    dead_letter_at = %(dead_letter_at)s,
    last_worker_error = %(last_worker_error)s
WHERE attempt_id = %(attempt_id)s
"""
STAFF_INVITE_DELIVERY_OUTBOX_COLUMNS = (
    *STAFF_INVITE_DELIVERY_ATTEMPT_COLUMNS,
    "email",
    "role",
    "organization_id",
    "expires_at",
    "accepted_at",
    "revoked_at",
    "delivered_at",
    "last_delivery_event_type",
)
LIST_STAFF_INVITE_DELIVERY_OUTBOX_ATTEMPTS_SQL = """
SELECT
    attempts.attempt_id,
    attempts.invite_token,
    attempts.attempted_at,
    attempts.attempted_by,
    attempts.provider,
    attempts.status,
    attempts.channel,
    attempts.recipient,
    attempts.delivery_url_base,
    attempts.note,
    attempts.error,
    attempts.worker_status,
    attempts.worker_attempt_count,
    attempts.next_worker_run_at,
    attempts.dead_letter_at,
    attempts.last_worker_error,
    invites.email,
    invites.role,
    invites.organization_id,
    invites.expires_at,
    invites.accepted_at,
    invites.revoked_at,
    invites.delivered_at,
    (
        SELECT events.event_type
        FROM staff_invite_delivery_events AS events
        WHERE events.attempt_id = attempts.attempt_id
        ORDER BY events.received_at DESC, events.event_id DESC
        LIMIT 1
    ) AS last_delivery_event_type
FROM staff_invite_delivery_attempts AS attempts
JOIN staff_invites AS invites
    ON invites.token = attempts.invite_token
ORDER BY
    CASE
        WHEN attempts.next_worker_run_at IS NULL THEN 1
        ELSE 0
    END,
    attempts.next_worker_run_at ASC,
    attempts.attempted_at DESC,
    attempts.attempt_id DESC
"""
STAFF_INVITE_DELIVERY_EVENT_COLUMNS = (
    "event_id",
    "provider",
    "provider_event_id",
    "attempt_id",
    "invite_token",
    "event_type",
    "mapped_attempt_status",
    "received_at",
    "occurred_at",
    "recipient",
    "error",
    "metadata_json",
)
STAFF_INVITE_DELIVERY_EVENT_SELECT = """
SELECT
    event_id,
    provider,
    provider_event_id,
    attempt_id,
    invite_token,
    event_type,
    mapped_attempt_status,
    received_at,
    occurred_at,
    recipient,
    error,
    metadata_json
FROM staff_invite_delivery_events
"""
GET_STAFF_INVITE_DELIVERY_EVENT_SQL = (
    STAFF_INVITE_DELIVERY_EVENT_SELECT
    + """
WHERE event_id = %(event_id)s
"""
)
GET_STAFF_INVITE_DELIVERY_EVENT_ID_BY_PROVIDER_SQL = """
SELECT event_id
FROM staff_invite_delivery_events
WHERE provider = %(provider)s AND provider_event_id = %(provider_event_id)s
"""
LIST_STAFF_INVITE_DELIVERY_EVENTS_SQL = (
    STAFF_INVITE_DELIVERY_EVENT_SELECT
    + """
WHERE invite_token = %(token)s
ORDER BY received_at DESC, event_id DESC
"""
)
RECORD_STAFF_INVITE_DELIVERY_EVENT_SQL = """
INSERT INTO staff_invite_delivery_events (
    event_id,
    provider,
    provider_event_id,
    attempt_id,
    invite_token,
    event_type,
    mapped_attempt_status,
    received_at,
    occurred_at,
    recipient,
    error,
    metadata_json
)
VALUES (
    %(event_id)s,
    %(provider)s,
    %(provider_event_id)s,
    %(attempt_id)s,
    %(token)s,
    %(event_type)s,
    %(mapped_attempt_status)s,
    %(received_at)s,
    %(occurred_at)s,
    %(recipient)s,
    %(error)s,
    %(metadata_json)s::jsonb
)
"""
APPLICATION_COLUMNS = (
    "id",
    "borrower_email",
    "status",
    "requested_amount",
    "purpose",
    "district",
    "settlement_type",
    "organization_id",
    "behavioral_signals_json",
    "score_result_json",
    "created_at",
    "scored_at",
)
APPLICATION_SELECT = """
SELECT
    id,
    borrower_email,
    status,
    requested_amount,
    purpose,
    district,
    settlement_type,
    organization_id,
    behavioral_signals_json,
    score_result_json,
    created_at,
    scored_at
FROM loan_applications
"""
GET_APPLICATION_SQL = APPLICATION_SELECT + "WHERE id = %(application_id)s"
LIST_APPLICATIONS_SQL = (
    APPLICATION_SELECT
    + """
ORDER BY created_at DESC
"""
)
LIST_APPLICATIONS_BY_ORGANIZATION_SQL = (
    APPLICATION_SELECT
    + """
WHERE organization_id = %(organization_id)s
ORDER BY created_at DESC
"""
)
LIST_BORROWER_APPLICATIONS_SQL = (
    APPLICATION_SELECT
    + """
WHERE borrower_email = %(borrower_email)s
ORDER BY created_at DESC
"""
)
CREATE_APPLICATION_SQL = """
INSERT INTO loan_applications (
    id,
    borrower_email,
    status,
    requested_amount,
    purpose,
    district,
    settlement_type,
    organization_id,
    behavioral_signals_json,
    score_result_json,
    created_at,
    scored_at
)
VALUES (
    %(application_id)s,
    %(borrower_email)s,
    'submitted',
    %(requested_amount)s,
    %(purpose)s,
    %(district)s,
    %(settlement_type)s,
    %(organization_id)s,
    %(behavioral_signals_json)s::jsonb,
    NULL,
    %(created_at)s,
    NULL
)
"""
ASSIGN_APPLICATION_ORGANIZATION_SQL = """
UPDATE loan_applications
SET organization_id = %(organization_id)s
WHERE id = %(application_id)s
"""
COUNT_APPLICATIONS_SQL = """
SELECT COUNT(*) AS count
FROM loan_applications
"""
DELETE_APPLICATIONS_SQL = """
DELETE FROM loan_applications
"""
GET_APPLICATION_SCORE_STATE_SQL = """
SELECT status, score_result_json
FROM loan_applications
WHERE id = %(application_id)s
"""
UPDATE_APPLICATION_SCORE_SQL = """
UPDATE loan_applications
SET
    status = %(status)s,
    score_result_json = %(score_result_json)s::jsonb,
    scored_at = %(scored_at)s
WHERE id = %(application_id)s
"""
APPLICATION_DECISION_COLUMNS = (
    "id",
    "application_id",
    "actor_email",
    "decision",
    "policy_name",
    "note",
    "created_at",
)
LIST_APPLICATION_DECISIONS_SQL = """
SELECT
    id,
    application_id,
    actor_email,
    decision,
    policy_name,
    note,
    created_at
FROM application_decisions
WHERE application_id = %(application_id)s
ORDER BY id ASC
"""
GET_LATEST_APPLICATION_DECISION_SQL = """
SELECT
    id,
    application_id,
    actor_email,
    decision,
    policy_name,
    note,
    created_at
FROM application_decisions
WHERE application_id = %(application_id)s
ORDER BY id DESC
LIMIT 1
"""
RECORD_APPLICATION_DECISION_SQL = """
INSERT INTO application_decisions (
    application_id,
    actor_email,
    decision,
    policy_name,
    note,
    created_at
)
VALUES (
    %(application_id)s,
    %(actor_email)s,
    %(decision)s,
    %(policy_name)s,
    %(note)s,
    %(created_at)s
)
"""
UPDATE_APPLICATION_STATUS_SQL = """
UPDATE loan_applications
SET status = %(status)s
WHERE id = %(application_id)s
"""
LIST_APPLICATION_TIMELINE_SQL = """
SELECT
    id,
    actor_email,
    action,
    entity_type,
    entity_id,
    details_json,
    created_at
FROM audit_events
WHERE entity_type = 'loan_application'
  AND entity_id = %(application_id)s
ORDER BY id ASC
"""
MODEL_VERSION_COLUMNS = (
    "version",
    "model_name",
    "model_type",
    "lifecycle_status",
    "is_active",
    "feature_schema_version",
    "training_data_label",
    "random_state",
    "metrics_json",
    "limitations_json",
    "created_by",
    "created_at",
    "activated_at",
)
MODEL_VERSION_SELECT = """
SELECT
    version,
    model_name,
    model_type,
    lifecycle_status,
    is_active,
    feature_schema_version,
    training_data_label,
    random_state,
    metrics_json,
    limitations_json,
    created_by,
    created_at,
    activated_at
FROM model_versions
"""
GET_MODEL_VERSION_SQL = MODEL_VERSION_SELECT + "WHERE version = %(version)s"
GET_MODEL_VERSION_EXISTS_SQL = """
SELECT version
FROM model_versions
WHERE version = %(version)s
"""
GET_ACTIVE_MODEL_VERSION_SQL = (
    MODEL_VERSION_SELECT
    + """
WHERE is_active IS TRUE
ORDER BY activated_at DESC NULLS LAST, created_at DESC, version DESC
LIMIT 1
"""
)
LIST_MODEL_VERSIONS_SQL = (
    MODEL_VERSION_SELECT
    + """
ORDER BY is_active DESC, created_at DESC, version DESC
"""
)
CREATE_MODEL_VERSION_SQL = """
INSERT INTO model_versions (
    version,
    model_name,
    model_type,
    lifecycle_status,
    is_active,
    feature_schema_version,
    training_data_label,
    random_state,
    metrics_json,
    limitations_json,
    created_by,
    created_at,
    activated_at
)
VALUES (
    %(version)s,
    %(model_name)s,
    'logistic_regression',
    'candidate',
    FALSE,
    %(feature_schema_version)s,
    %(training_data_label)s,
    %(random_state)s,
    %(metrics_json)s::jsonb,
    %(limitations_json)s::jsonb,
    %(created_by)s,
    %(created_at)s,
    NULL
)
"""
DEACTIVATE_OTHER_MODEL_VERSIONS_SQL = """
UPDATE model_versions
SET lifecycle_status = 'inactive', is_active = FALSE
WHERE is_active IS TRUE AND version <> %(version)s
"""
ACTIVATE_MODEL_VERSION_SQL = """
UPDATE model_versions
SET lifecycle_status = 'active', is_active = TRUE, activated_at = %(activated_at)s
WHERE version = %(version)s
"""
AUDIT_EVENT_COLUMNS = (
    "id",
    "actor_email",
    "action",
    "entity_type",
    "entity_id",
    "details_json",
    "created_at",
)
AUDIT_EVENT_SELECT = """
SELECT
    id,
    actor_email,
    action,
    entity_type,
    entity_id,
    details_json,
    created_at
FROM audit_events
"""
LIST_AUDIT_EVENTS_SQL = (
    AUDIT_EVENT_SELECT
    + """
ORDER BY id DESC
"""
)
RECORD_AUDIT_EVENT_SQL = """
INSERT INTO audit_events (
    actor_email,
    action,
    entity_type,
    entity_id,
    details_json,
    created_at
)
VALUES (
    %(actor_email)s,
    %(action)s,
    %(entity_type)s,
    %(entity_id)s,
    %(details_json)s::jsonb,
    %(created_at)s
)
"""


@dataclass(frozen=True)
class RepositoryMethodGroup:
    key: str
    label: str
    methods: tuple[str, ...]

    def as_dict(
        self,
        implemented_methods: tuple[str, ...] = (),
    ) -> dict[str, object]:
        implemented_method_set = set(implemented_methods)
        implemented = [
            method for method in self.methods if method in implemented_method_set
        ]
        pending = [
            method for method in self.methods if method not in implemented_method_set
        ]
        return {
            "key": self.key,
            "label": self.label,
            "method_count": len(self.methods),
            "methods": list(self.methods),
            "implemented_method_count": len(implemented),
            "implemented_methods": implemented,
            "pending_method_count": len(pending),
            "pending_methods": pending,
        }


REPOSITORY_METHOD_GROUPS: tuple[RepositoryMethodGroup, ...] = (
    RepositoryMethodGroup(
        key="identity_access",
        label="Identity, MFA, and session lifecycle",
        methods=(
            "create_user",
            "get_user",
            "list_users",
            "disable_user",
            "reactivate_user",
            "attest_user_mfa",
            "create_session",
            "get_user_by_token",
            "list_active_sessions",
            "revoke_session",
            "revoke_session_by_id",
        ),
    ),
    RepositoryMethodGroup(
        key="organizations",
        label="MFI organization and tenant assignment",
        methods=(
            "create_organization",
            "get_organization",
            "list_organizations",
            "assign_user_organization",
        ),
    ),
    RepositoryMethodGroup(
        key="staff_invites_delivery",
        label="Staff invites, delivery outbox, worker, and webhooks",
        methods=(
            "create_staff_invite",
            "get_staff_invite",
            "list_staff_invites",
            "mark_staff_invite_accepted",
            "mark_staff_invite_revoked",
            "mark_staff_invite_delivered",
            "record_staff_invite_delivery_attempt",
            "record_staff_invite_delivery_event",
            "get_staff_invite_delivery_attempt",
            "get_staff_invite_delivery_event",
            "list_staff_invite_delivery_attempts",
            "list_staff_invite_delivery_events",
            "list_staff_invite_delivery_outbox_attempts",
            "update_staff_invite_delivery_attempt_status",
            "update_staff_invite_delivery_worker_state",
        ),
    ),
    RepositoryMethodGroup(
        key="application_lifecycle",
        label="Borrower application lifecycle, scoring, review, and decisions",
        methods=(
            "create_application",
            "get_application",
            "list_applications",
            "list_borrower_applications",
            "assign_application_organization",
            "update_application_score",
            "record_application_decision",
            "list_application_decisions",
            "list_application_timeline",
            "clear_applications",
        ),
    ),
    RepositoryMethodGroup(
        key="model_registry",
        label="Model registry and active-version governance",
        methods=(
            "create_model_version",
            "get_model_version",
            "get_active_model_version",
            "list_model_versions",
            "activate_model_version",
        ),
    ),
    RepositoryMethodGroup(
        key="portfolio_analytics",
        label="Portfolio simulations and MFI analytics",
        methods=(
            "create_portfolio_simulation",
            "get_portfolio_simulation",
            "list_portfolio_simulations",
            "segment_analytics",
            "decision_analytics",
        ),
    ),
    RepositoryMethodGroup(
        key="audit",
        label="Audit event recording and review",
        methods=(
            "record_audit_event",
            "list_audit_events",
        ),
    ),
)


def repository_contract_methods() -> tuple[str, ...]:
    return tuple(
        method
        for group in REPOSITORY_METHOD_GROUPS
        for method in group.methods
    )


def repository_implemented_methods() -> tuple[str, ...]:
    return POSTGRESQL_REPOSITORY_IMPLEMENTED_METHODS


def repository_contract_summary() -> dict[str, object]:
    methods = repository_contract_methods()
    implemented_methods = repository_implemented_methods()
    read_only_methods = (
        *POSTGRESQL_MODEL_REGISTRY_READ_METHODS,
        *POSTGRESQL_AUDIT_READ_METHODS,
        *POSTGRESQL_ORGANIZATION_READ_METHODS,
        *POSTGRESQL_IDENTITY_READ_METHODS,
        *POSTGRESQL_STAFF_INVITE_READ_METHODS,
        *POSTGRESQL_APPLICATION_LIFECYCLE_READ_METHODS,
    )
    write_methods = (
        *POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS,
        *POSTGRESQL_AUDIT_WRITE_METHODS,
        *POSTGRESQL_ORGANIZATION_WRITE_METHODS,
        *POSTGRESQL_IDENTITY_WRITE_METHODS,
        *POSTGRESQL_STAFF_INVITE_WRITE_METHODS,
        *POSTGRESQL_APPLICATION_LIFECYCLE_WRITE_METHODS,
    )
    completed_groups = [
        group.key
        for group in REPOSITORY_METHOD_GROUPS
        if all(method in implemented_methods for method in group.methods)
    ]
    return {
        "module": POSTGRESQL_REPOSITORY_ADAPTER_MODULE,
        "version": POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        "status": POSTGRESQL_REPOSITORY_ADAPTER_STATUS,
        "stage": POSTGRESQL_REPOSITORY_ADAPTER_STAGE,
        "present": True,
        "runtime_enabled": False,
        "method_count": len(methods),
        "implemented_method_count": len(implemented_methods),
        "implemented_methods": list(implemented_methods),
        "pending_method_count": len(methods) - len(implemented_methods),
        "completed_method_group_count": len(completed_groups),
        "completed_method_groups": completed_groups,
        "read_only_method_count": len(read_only_methods),
        "read_only_methods": list(read_only_methods),
        "write_method_count": len(write_methods),
        "write_methods": list(write_methods),
        "method_groups": [
            group.as_dict(implemented_methods)
            for group in REPOSITORY_METHOD_GROUPS
        ],
        "limitation": POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION,
    }


def _coerce_json(value: object, fallback: object) -> object:
    if value is None:
        return fallback
    if isinstance(value, str):
        return json.loads(value)
    return value


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "t", "true", "yes", "y"}
    return bool(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def configured_session_ttl_hours() -> float:
    raw_value = os.environ.get("MICROSCORE_SESSION_TTL_HOURS", "").strip()
    if not raw_value:
        return DEFAULT_SESSION_TTL_HOURS
    try:
        value = float(raw_value)
    except ValueError:
        return DEFAULT_SESSION_TTL_HOURS
    return value if value > 0 else DEFAULT_SESSION_TTL_HOURS


def session_expiry_metadata(
    created_at: str | None = None,
    *,
    ttl_hours: float | None = None,
) -> dict[str, Any]:
    session_created_at = (
        _parse_utc_datetime(created_at) if created_at else datetime.now(timezone.utc)
    )
    ttl = ttl_hours if ttl_hours is not None else configured_session_ttl_hours()
    expires_at = session_created_at + timedelta(hours=ttl)
    return {
        "session_created_at": session_created_at.isoformat(),
        "session_expires_at": expires_at.isoformat(),
        "session_ttl_seconds": max(1, int(round(ttl * 3600))),
    }


def _initial_delivery_worker_state(status: str, attempted_at: str) -> dict[str, Any]:
    if status == "queued":
        return {
            "worker_status": "queued",
            "worker_attempt_count": 0,
            "next_worker_run_at": attempted_at,
            "dead_letter_at": None,
            "last_worker_error": None,
        }
    return {
        "worker_status": "completed",
        "worker_attempt_count": 0,
        "next_worker_run_at": None,
        "dead_letter_at": None,
        "last_worker_error": None,
    }


def _row_to_mapping(
    row: object,
    columns: tuple[str, ...] = MODEL_VERSION_COLUMNS,
) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "keys") and hasattr(row, "__getitem__"):
        return {str(key): row[key] for key in row.keys()}
    if isinstance(row, tuple):
        return dict(zip(columns, row))
    if isinstance(row, list):
        return dict(zip(columns, row))
    raise TypeError(f"Unsupported PostgreSQL row type: {type(row).__name__}")


def postgres_model_version_from_row(row: object) -> dict[str, Any]:
    model_version = _row_to_mapping(row)
    model_version["is_active"] = _coerce_bool(model_version["is_active"])
    model_version["metrics"] = (
        _coerce_json(model_version.pop("metrics_json"), {}) or {}
    )
    model_version["limitations"] = (
        _coerce_json(model_version.pop("limitations_json"), []) or []
    )
    return model_version


def postgres_audit_event_from_row(row: object) -> dict[str, Any]:
    event = _row_to_mapping(row, AUDIT_EVENT_COLUMNS)
    event["details"] = _coerce_json(event.pop("details_json"), {}) or {}
    return event


def postgres_organization_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, ORGANIZATION_COLUMNS)


def postgres_user_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, USER_COLUMNS)


def postgres_list_user_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, LIST_USER_COLUMNS)


def postgres_session_user_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, SESSION_USER_COLUMNS)


def postgres_active_session_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, ACTIVE_SESSION_COLUMNS)


def postgres_staff_invite_from_row(row: object) -> dict[str, Any]:
    invite = _row_to_mapping(row, STAFF_INVITE_COLUMNS)
    invite["delivery_attempt_count"] = int(
        invite.get("delivery_attempt_count") or 0
    )
    invite["delivery_event_count"] = int(invite.get("delivery_event_count") or 0)
    return invite


def postgres_staff_invite_delivery_attempt_from_row(row: object) -> dict[str, Any]:
    attempt = _row_to_mapping(row, STAFF_INVITE_DELIVERY_ATTEMPT_COLUMNS)
    attempt["worker_attempt_count"] = int(
        attempt.get("worker_attempt_count") or 0
    )
    return attempt


def postgres_staff_invite_delivery_outbox_attempt_from_row(
    row: object,
) -> dict[str, Any]:
    attempt = _row_to_mapping(row, STAFF_INVITE_DELIVERY_OUTBOX_COLUMNS)
    attempt["worker_attempt_count"] = int(
        attempt.get("worker_attempt_count") or 0
    )
    return attempt


def postgres_staff_invite_delivery_event_from_row(row: object) -> dict[str, Any]:
    event = _row_to_mapping(row, STAFF_INVITE_DELIVERY_EVENT_COLUMNS)
    event["metadata"] = _coerce_json(event.pop("metadata_json"), {}) or {}
    return event


def postgres_application_decision_from_row(row: object) -> dict[str, Any]:
    return _row_to_mapping(row, APPLICATION_DECISION_COLUMNS)


def postgres_application_from_row(row: object) -> dict[str, Any]:
    application = _row_to_mapping(row, APPLICATION_COLUMNS)
    if application.get("requested_amount") is not None:
        application["requested_amount"] = float(application["requested_amount"])
    application["behavioral_signals"] = (
        _coerce_json(application.pop("behavioral_signals_json"), {}) or {}
    )
    application["score_result"] = _coerce_json(
        application.pop("score_result_json"),
        None,
    )
    return application


def model_registry_read_parity_snapshot(repository: object) -> dict[str, object]:
    versions = getattr(repository, "list_model_versions")()
    active = getattr(repository, "get_active_model_version")()
    active_lookup = None
    if active:
        active_lookup = getattr(repository, "get_model_version")(active["version"])
    return {
        "method_group": "model_registry",
        "implemented_methods": list(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "version_count": len(versions),
        "versions": [row["version"] for row in versions],
        "active_version": active["version"] if active else None,
        "active_is_marked": bool(active and active.get("is_active")),
        "active_lookup_matches": active == active_lookup if active else active_lookup is None,
    }


def model_registry_method_group_parity_snapshot(repository: object) -> dict[str, object]:
    snapshot = model_registry_read_parity_snapshot(repository)
    snapshot["implemented_methods"] = list(POSTGRESQL_MODEL_REGISTRY_METHODS)
    snapshot["write_methods"] = list(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS)
    snapshot["method_group_complete"] = True
    return snapshot


def audit_method_group_parity_snapshot(repository: object) -> dict[str, object]:
    events = getattr(repository, "list_audit_events")()
    return {
        "method_group": "audit",
        "implemented_methods": list(POSTGRESQL_AUDIT_METHODS),
        "event_count": len(events),
        "actions": [event["action"] for event in events],
        "entities": [
            f"{event['entity_type']}:{event.get('entity_id') or ''}"
            for event in events
        ],
        "details_keys": [
            sorted((event.get("details") or {}).keys())
            for event in events
        ],
        "method_group_complete": True,
    }


def _organization_identity(organization: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if organization is None:
        return None
    return {
        "id": organization["id"],
        "name": organization["name"],
        "region": organization["region"],
    }


def organization_method_group_parity_snapshot(repository: object) -> dict[str, object]:
    organizations = getattr(repository, "list_organizations")()
    lookups = [
        getattr(repository, "get_organization")(organization["id"])
        for organization in organizations
    ]
    return {
        "method_group": "organizations",
        "implemented_methods": list(POSTGRESQL_ORGANIZATION_METHODS),
        "organization_count": len(organizations),
        "organization_ids": [organization["id"] for organization in organizations],
        "organization_names": [organization["name"] for organization in organizations],
        "organization_regions": [
            organization["region"] for organization in organizations
        ],
        "lookup_matches": [
            _organization_identity(lookup) == _organization_identity(organization)
            for lookup, organization in zip(lookups, organizations)
        ],
        "method_group_complete": True,
    }


def identity_access_method_group_parity_snapshot(
    repository: object,
    *,
    now: datetime | None = None,
    ttl_hours: float | None = None,
) -> dict[str, object]:
    users = getattr(repository, "list_users")()
    active_sessions = getattr(repository, "list_active_sessions")(
        now=now,
        ttl_hours=ttl_hours,
    )
    staff_sessions = getattr(repository, "list_active_sessions")(
        staff_only=True,
        now=now,
        ttl_hours=ttl_hours,
    )
    return {
        "method_group": "identity_access",
        "implemented_methods": list(POSTGRESQL_IDENTITY_METHODS),
        "user_count": len(users),
        "user_emails": [user["email"] for user in users],
        "user_roles": [user["role"] for user in users],
        "user_organization_ids": [user.get("organization_id") for user in users],
        "disabled_users": [
            user["email"] for user in users if user.get("disabled_at") is not None
        ],
        "mfa_attested_users": [
            user["email"] for user in users if user.get("mfa_attested_at") is not None
        ],
        "active_session_count": len(active_sessions),
        "active_session_emails": [
            session["email"] for session in active_sessions
        ],
        "active_session_ids": [
            session["session_id"] for session in active_sessions
        ],
        "staff_session_count": len(staff_sessions),
        "staff_session_emails": [
            session["email"] for session in staff_sessions
        ],
        "method_group_complete": True,
    }


def _staff_invite_state(invite: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if invite is None:
        return None
    return {
        "token": invite["token"],
        "email": invite["email"],
        "role": invite["role"],
        "organization_id": invite["organization_id"],
        "accepted": invite.get("accepted_at") is not None,
        "revoked": invite.get("revoked_at") is not None,
        "delivered": invite.get("delivered_at") is not None,
        "delivery_channel": invite.get("delivery_channel"),
        "delivery_attempt_count": int(invite.get("delivery_attempt_count") or 0),
        "last_delivery_status": invite.get("last_delivery_status"),
        "last_delivery_provider": invite.get("last_delivery_provider"),
        "delivery_event_count": int(invite.get("delivery_event_count") or 0),
        "last_delivery_event_type": invite.get("last_delivery_event_type"),
    }


def staff_invites_delivery_method_group_parity_snapshot(
    repository: object,
    token: str,
) -> dict[str, object]:
    invites = getattr(repository, "list_staff_invites")()
    attempts = getattr(repository, "list_staff_invite_delivery_attempts")(token)
    events = getattr(repository, "list_staff_invite_delivery_events")(token)
    outbox_attempts = getattr(repository, "list_staff_invite_delivery_outbox_attempts")()
    return {
        "method_group": "staff_invites_delivery",
        "implemented_methods": list(POSTGRESQL_STAFF_INVITE_METHODS),
        "invite_count": len(invites),
        "invite_tokens": sorted(invite["token"] for invite in invites),
        "invite_states": [
            _staff_invite_state(invite)
            for invite in sorted(invites, key=lambda item: str(item["token"]))
        ],
        "lookup": _staff_invite_state(getattr(repository, "get_staff_invite")(token)),
        "attempt_count": len(attempts),
        "attempt_ids": [attempt["attempt_id"] for attempt in attempts],
        "attempt_statuses": [attempt["status"] for attempt in attempts],
        "attempt_worker_statuses": [
            attempt["worker_status"] for attempt in attempts
        ],
        "attempt_worker_counts": [
            int(attempt.get("worker_attempt_count") or 0)
            for attempt in attempts
        ],
        "outbox_attempt_ids": [
            attempt["attempt_id"] for attempt in outbox_attempts
        ],
        "outbox_worker_statuses": [
            attempt["worker_status"] for attempt in outbox_attempts
        ],
        "event_count": len(events),
        "event_ids": [event["event_id"] for event in events],
        "event_types": [event["event_type"] for event in events],
        "event_mapped_statuses": [
            event["mapped_attempt_status"] for event in events
        ],
        "event_metadata_keys": [
            sorted((event.get("metadata") or {}).keys())
            for event in events
        ],
        "method_group_complete": True,
    }


def _application_state(
    application: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if application is None:
        return None
    score_result = application.get("score_result") or {}
    decision_result = application.get("decision_result") or {}
    return {
        "id": application["id"],
        "borrower_email": application["borrower_email"],
        "status": application["status"],
        "requested_amount": float(application["requested_amount"]),
        "purpose": application["purpose"],
        "district": application.get("district"),
        "settlement_type": application.get("settlement_type"),
        "organization_id": application.get("organization_id"),
        "behavioral_signal_keys": sorted(
            (application.get("behavioral_signals") or {}).keys()
        ),
        "has_score": bool(application.get("score_result")),
        "risk_band": score_result.get("risk_band"),
        "model_version": score_result.get("model_version"),
        "decision": decision_result.get("decision"),
        "policy_name": decision_result.get("policy_name"),
    }


def application_lifecycle_method_group_parity_snapshot(
    repository: object,
    *,
    application_id: str,
    borrower_email: str,
    organization_id: str,
) -> dict[str, object]:
    applications = getattr(repository, "list_applications")()
    organization_applications = getattr(repository, "list_applications")(
        organization_id,
    )
    borrower_applications = getattr(repository, "list_borrower_applications")(
        borrower_email,
    )
    decisions = getattr(repository, "list_application_decisions")(application_id)
    timeline = getattr(repository, "list_application_timeline")(application_id)
    return {
        "method_group": "application_lifecycle",
        "implemented_methods": list(POSTGRESQL_APPLICATION_LIFECYCLE_METHODS),
        "application_count": len(applications),
        "application_ids": sorted(application["id"] for application in applications),
        "application_states": [
            _application_state(application)
            for application in sorted(
                applications,
                key=lambda item: str(item["id"]),
            )
        ],
        "lookup": _application_state(
            getattr(repository, "get_application")(application_id)
        ),
        "organization_application_ids": sorted(
            application["id"] for application in organization_applications
        ),
        "borrower_application_ids": sorted(
            application["id"] for application in borrower_applications
        ),
        "decision_count": len(decisions),
        "decision_values": [decision["decision"] for decision in decisions],
        "decision_policies": [decision.get("policy_name") for decision in decisions],
        "timeline_count": len(timeline),
        "timeline_actions": [event["action"] for event in timeline],
        "timeline_detail_keys": [
            sorted((event.get("details") or {}).keys()) for event in timeline
        ],
        "method_group_complete": True,
    }


class PostgresRepositoryAdapter:
    """Partial PostgreSQL adapter for completed method-group parity tests.

    The adapter intentionally accepts an injected connection factory rather than
    opening ``MICROSCORE_DATABASE_URL`` by itself. That keeps the production
    backend disabled while still letting parity tests execute the first
    repository method groups.
    """

    def __init__(self, connection_factory: Callable[[], Any] | None = None) -> None:
        self._connection_factory = connection_factory

    @property
    def backend(self) -> str:
        return "postgresql"

    def describe_contract(self) -> dict[str, object]:
        return {
            **repository_contract_summary(),
            "backend": self.backend,
            "database_url_env": "MICROSCORE_DATABASE_URL",
        }

    @contextmanager
    def _connection(self) -> Any:
        if self._connection_factory is None:
            raise RuntimeError(
                "PostgreSQL repository adapter requires an injected "
                "connection_factory for parity tests. Runtime backend selection "
                "is still disabled."
            )
        connection = self._connection_factory()
        try:
            yield connection
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _execute(connection: object, sql: str, params: dict[str, object]) -> object:
        execute = getattr(connection, "execute", None)
        if callable(execute):
            return execute(sql, params)
        cursor = connection.cursor()
        cursor.execute(sql, params)
        return cursor

    def _fetchone(
        self,
        sql: str,
        params: dict[str, object] | None = None,
    ) -> object | None:
        with self._connection() as connection:
            cursor = self._execute(connection, sql, params or {})
            try:
                return cursor.fetchone()
            finally:
                close = getattr(cursor, "close", None)
                if callable(close):
                    close()

    def _fetchall(
        self,
        sql: str,
        params: dict[str, object] | None = None,
    ) -> list[object]:
        with self._connection() as connection:
            cursor = self._execute(connection, sql, params or {})
            try:
                return list(cursor.fetchall())
            finally:
                close = getattr(cursor, "close", None)
                if callable(close):
                    close()

    def _write(
        self,
        statements: list[tuple[str, dict[str, object]]],
    ) -> None:
        self._write_with_rowcounts(statements)

    def _write_with_rowcounts(
        self,
        statements: list[tuple[str, dict[str, object]]],
    ) -> list[int]:
        rowcounts: list[int] = []
        with self._connection() as connection:
            try:
                for sql, params in statements:
                    cursor = self._execute(connection, sql, params)
                    rowcounts.append(int(getattr(cursor, "rowcount", 0) or 0))
                    close = getattr(cursor, "close", None)
                    if callable(close):
                        close()
                commit = getattr(connection, "commit", None)
                if callable(commit):
                    commit()
            except Exception:
                rollback = getattr(connection, "rollback", None)
                if callable(rollback):
                    rollback()
                raise
        return rowcounts

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_USER_SQL,
                    {
                        "email": email,
                        "password_hash": password_hash,
                        "role": role,
                        "organization_id": organization_id,
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        self.record_audit_event(
            actor_email=email,
            action="user_registered",
            entity_type="user",
            entity_id=email,
            details={"role": role, "organization_id": organization_id},
        )
        return self.get_user(email) or {}

    def get_user(self, email: str) -> dict[str, Any] | None:
        row = self._fetchone(GET_USER_SQL, {"email": email})
        return postgres_user_from_row(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        return [
            postgres_list_user_from_row(row)
            for row in self._fetchall(LIST_USERS_SQL)
        ]

    def disable_user(self, email: str, disabled_by: str) -> dict[str, Any] | None:
        existing = self._fetchone(GET_USER_DISABLE_STATUS_SQL, {"email": email})
        if existing is None:
            return None
        existing_status = _row_to_mapping(existing, ("email", "disabled_at"))
        if existing_status["disabled_at"] is None:
            self._write(
                [
                    (
                        DISABLE_USER_SQL,
                        {
                            "email": email,
                            "disabled_at": _now_iso(),
                            "disabled_by": disabled_by,
                        },
                    )
                ]
            )
        revoked_counts = self._write_with_rowcounts(
            [(DELETE_SESSIONS_BY_EMAIL_SQL, {"email": email})]
        )
        disabled = self.get_user(email) or {}
        disabled["revoked_session_count"] = revoked_counts[0] if revoked_counts else 0
        disabled["was_already_disabled"] = (
            existing_status["disabled_at"] is not None
        )
        return disabled

    def reactivate_user(self, email: str) -> dict[str, Any] | None:
        existing = self._fetchone(GET_USER_REACTIVATE_STATUS_SQL, {"email": email})
        if existing is None:
            return None
        existing_status = _row_to_mapping(
            existing,
            ("email", "disabled_at", "disabled_by"),
        )
        if existing_status["disabled_at"] is not None:
            self._write([(REACTIVATE_USER_SQL, {"email": email})])
        reactivated = self.get_user(email) or {}
        reactivated["was_already_active"] = existing_status["disabled_at"] is None
        reactivated["previous_disabled_at"] = existing_status["disabled_at"]
        reactivated["previous_disabled_by"] = existing_status["disabled_by"]
        return reactivated

    def attest_user_mfa(
        self,
        email: str,
        attested_by: str,
        method: str,
    ) -> dict[str, Any] | None:
        existing = self._fetchone(GET_USER_MFA_STATUS_SQL, {"email": email})
        if existing is None:
            return None
        existing_status = _row_to_mapping(existing, ("email", "mfa_attested_at"))
        if existing_status["mfa_attested_at"] is None:
            self._write(
                [
                    (
                        ATTEST_USER_MFA_SQL,
                        {
                            "email": email,
                            "mfa_attested_at": _now_iso(),
                            "mfa_attested_by": attested_by,
                            "mfa_method": method,
                        },
                    )
                ]
            )
        attested = self.get_user(email) or {}
        attested["was_already_attested"] = (
            existing_status["mfa_attested_at"] is not None
        )
        return attested

    def create_session(
        self,
        token: str,
        email: str,
        *,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        stored_created_at = created_at or _now_iso()
        self._write(
            [
                (
                    CREATE_SESSION_SQL,
                    {
                        "token": token,
                        "email": email,
                        "created_at": stored_created_at,
                    },
                )
            ]
        )
        return session_expiry_metadata(stored_created_at)

    def get_user_by_token(
        self,
        token: str,
        *,
        now: datetime | None = None,
        ttl_hours: float | None = None,
    ) -> dict[str, Any] | None:
        row = self._fetchone(GET_USER_BY_TOKEN_SQL, {"token": token})
        if row is None:
            return None
        user = postgres_session_user_from_row(row)
        if user["disabled_at"] is not None:
            self.revoke_session(token)
            return None
        metadata = session_expiry_metadata(
            user["session_created_at"],
            ttl_hours=ttl_hours,
        )
        expires_at = _parse_utc_datetime(metadata["session_expires_at"])
        if expires_at <= (now or datetime.now(timezone.utc)):
            self.revoke_session(token)
            return None
        user.update(metadata)
        return user

    def revoke_session(self, token: str) -> bool:
        rowcounts = self._write_with_rowcounts(
            [(DELETE_SESSION_BY_TOKEN_SQL, {"token": token})]
        )
        return bool(rowcounts and rowcounts[0] > 0)

    def list_active_sessions(
        self,
        *,
        staff_only: bool = False,
        now: datetime | None = None,
        ttl_hours: float | None = None,
    ) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        rows = self._fetchall(LIST_ACTIVE_SESSIONS_SQL)
        active_sessions: list[dict[str, Any]] = []
        expired_or_disabled_tokens: list[str] = []
        for row in rows:
            session = postgres_active_session_from_row(row)
            if session["disabled_at"] is not None:
                expired_or_disabled_tokens.append(str(session["token"]))
                continue
            if staff_only and session["role"] not in STAFF_ROLES:
                continue
            metadata = session_expiry_metadata(
                session["session_created_at"],
                ttl_hours=ttl_hours,
            )
            expires_at = _parse_utc_datetime(metadata["session_expires_at"])
            if expires_at <= now:
                expired_or_disabled_tokens.append(str(session["token"]))
                continue
            session.update(metadata)
            session["session_id"] = hashlib.sha256(
                str(session["token"]).encode("utf-8")
            ).hexdigest()
            active_sessions.append(session)

        for token in expired_or_disabled_tokens:
            self.revoke_session(token)
        return active_sessions

    def revoke_session_by_id(
        self,
        session_id: str,
        *,
        staff_only: bool = False,
    ) -> dict[str, Any] | None:
        normalized_session_id = session_id.strip().lower()
        for session in self.list_active_sessions(staff_only=staff_only):
            if session["session_id"] != normalized_session_id:
                continue
            if self.revoke_session(str(session["token"])):
                return session
            return None
        return None

    def get_model_version(self, version: str) -> dict[str, Any] | None:
        row = self._fetchone(GET_MODEL_VERSION_SQL, {"version": version})
        return postgres_model_version_from_row(row) if row else None

    def get_active_model_version(self) -> dict[str, Any] | None:
        row = self._fetchone(GET_ACTIVE_MODEL_VERSION_SQL)
        return postgres_model_version_from_row(row) if row else None

    def list_model_versions(self) -> list[dict[str, Any]]:
        return [
            postgres_model_version_from_row(row)
            for row in self._fetchall(LIST_MODEL_VERSIONS_SQL)
        ]

    def create_model_version(
        self,
        *,
        version: str,
        model_name: str,
        feature_schema_version: str,
        training_data_label: str,
        random_state: int,
        metrics: dict[str, Any],
        limitations: list[str],
        created_by: str,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_MODEL_VERSION_SQL,
                    {
                        "version": version,
                        "model_name": model_name,
                        "feature_schema_version": feature_schema_version,
                        "training_data_label": training_data_label,
                        "random_state": random_state,
                        "metrics_json": _json_dumps(metrics),
                        "limitations_json": _json_dumps(limitations),
                        "created_by": created_by,
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        return self.get_model_version(version) or {}

    def activate_model_version(self, version: str) -> dict[str, Any] | None:
        if self._fetchone(GET_MODEL_VERSION_EXISTS_SQL, {"version": version}) is None:
            return None
        self._write(
            [
                (DEACTIVATE_OTHER_MODEL_VERSIONS_SQL, {"version": version}),
                (
                    ACTIVATE_MODEL_VERSION_SQL,
                    {
                        "version": version,
                        "activated_at": _now_iso(),
                    },
                ),
            ]
        )
        return self.get_model_version(version)

    def record_audit_event(
        self,
        *,
        actor_email: str | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, Any],
    ) -> None:
        self._write(
            [
                (
                    RECORD_AUDIT_EVENT_SQL,
                    {
                        "actor_email": actor_email,
                        "action": action,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "details_json": _json_dumps(details),
                        "created_at": _now_iso(),
                    },
                )
            ]
        )

    def list_audit_events(self) -> list[dict[str, Any]]:
        return [
            postgres_audit_event_from_row(row)
            for row in self._fetchall(LIST_AUDIT_EVENTS_SQL)
        ]

    def create_organization(
        self,
        *,
        organization_id: str,
        name: str,
        region: str,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_ORGANIZATION_SQL,
                    {
                        "organization_id": organization_id,
                        "name": name,
                        "region": region,
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        return self.get_organization(organization_id) or {}

    def get_organization(self, organization_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            GET_ORGANIZATION_SQL,
            {"organization_id": organization_id},
        )
        return postgres_organization_from_row(row) if row else None

    def list_organizations(self) -> list[dict[str, Any]]:
        return [
            postgres_organization_from_row(row)
            for row in self._fetchall(LIST_ORGANIZATIONS_SQL)
        ]

    def assign_user_organization(
        self,
        email: str,
        organization_id: str | None,
    ) -> None:
        self._write(
            [
                (
                    ASSIGN_USER_ORGANIZATION_SQL,
                    {
                        "email": email,
                        "organization_id": organization_id,
                    },
                )
            ]
        )

    def create_staff_invite(
        self,
        *,
        token: str,
        email: str,
        role: str,
        organization_id: str,
        created_by: str,
        expires_at: str,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_STAFF_INVITE_SQL,
                    {
                        "token": token,
                        "email": email,
                        "role": role,
                        "organization_id": organization_id,
                        "created_by": created_by,
                        "created_at": _now_iso(),
                        "expires_at": expires_at,
                    },
                )
            ]
        )
        return self.get_staff_invite(token) or {}

    def get_staff_invite(self, token: str) -> dict[str, Any] | None:
        row = self._fetchone(GET_STAFF_INVITE_SQL, {"token": token})
        return postgres_staff_invite_from_row(row) if row else None

    def list_staff_invites(self) -> list[dict[str, Any]]:
        return [
            postgres_staff_invite_from_row(row)
            for row in self._fetchall(LIST_STAFF_INVITES_SQL)
        ]

    def mark_staff_invite_accepted(self, token: str, accepted_by: str) -> bool:
        rowcounts = self._write_with_rowcounts(
            [
                (
                    MARK_STAFF_INVITE_ACCEPTED_SQL,
                    {
                        "token": token,
                        "accepted_at": _now_iso(),
                        "accepted_by": accepted_by,
                    },
                )
            ]
        )
        return bool(rowcounts and rowcounts[0] > 0)

    def mark_staff_invite_revoked(self, token: str, revoked_by: str) -> bool:
        rowcounts = self._write_with_rowcounts(
            [
                (
                    MARK_STAFF_INVITE_REVOKED_SQL,
                    {
                        "token": token,
                        "revoked_at": _now_iso(),
                        "revoked_by": revoked_by,
                    },
                )
            ]
        )
        return bool(rowcounts and rowcounts[0] > 0)

    def mark_staff_invite_delivered(
        self,
        token: str,
        *,
        delivered_by: str | None,
        channel: str,
        recipient: str | None,
        url_base: str,
        note: str | None,
    ) -> dict[str, Any] | None:
        existing = self.get_staff_invite(token)
        if existing is None:
            return None
        was_already_delivered = existing.get("delivered_at") is not None
        if not was_already_delivered:
            self._write(
                [
                    (
                        MARK_STAFF_INVITE_DELIVERED_SQL,
                        {
                            "token": token,
                            "delivered_at": _now_iso(),
                            "delivered_by": delivered_by,
                            "channel": channel,
                            "recipient": recipient,
                            "url_base": url_base,
                            "note": note,
                        },
                    )
                ]
            )
        delivered = self.get_staff_invite(token) or existing
        delivered["was_already_delivered"] = was_already_delivered
        return delivered

    def record_staff_invite_delivery_attempt(
        self,
        *,
        attempt_id: str,
        token: str,
        attempted_by: str,
        provider: str,
        status: str,
        channel: str,
        recipient: str | None,
        url_base: str | None,
        note: str | None,
        error: str | None = None,
    ) -> dict[str, Any]:
        attempted_at = _now_iso()
        worker_state = _initial_delivery_worker_state(status, attempted_at)
        self._write(
            [
                (
                    RECORD_STAFF_INVITE_DELIVERY_ATTEMPT_SQL,
                    {
                        "attempt_id": attempt_id,
                        "token": token,
                        "attempted_at": attempted_at,
                        "attempted_by": attempted_by,
                        "provider": provider,
                        "status": status,
                        "channel": channel,
                        "recipient": recipient,
                        "url_base": url_base,
                        "note": note,
                        "error": error,
                        "worker_status": worker_state["worker_status"],
                        "worker_attempt_count": worker_state[
                            "worker_attempt_count"
                        ],
                        "next_worker_run_at": worker_state["next_worker_run_at"],
                        "dead_letter_at": worker_state["dead_letter_at"],
                        "last_worker_error": worker_state["last_worker_error"],
                    },
                )
            ]
        )
        return self.get_staff_invite_delivery_attempt(attempt_id) or {}

    def get_staff_invite_delivery_attempt(
        self,
        attempt_id: str,
    ) -> dict[str, Any] | None:
        row = self._fetchone(
            GET_STAFF_INVITE_DELIVERY_ATTEMPT_SQL,
            {"attempt_id": attempt_id},
        )
        return postgres_staff_invite_delivery_attempt_from_row(row) if row else None

    def list_staff_invite_delivery_attempts(
        self,
        token: str,
    ) -> list[dict[str, Any]]:
        return [
            postgres_staff_invite_delivery_attempt_from_row(row)
            for row in self._fetchall(
                LIST_STAFF_INVITE_DELIVERY_ATTEMPTS_SQL,
                {"token": token},
            )
        ]

    def update_staff_invite_delivery_attempt_status(
        self,
        attempt_id: str,
        *,
        status: str,
        error: str | None,
        worker_status: str | None = None,
        next_worker_run_at: str | None = None,
        dead_letter_at: str | None = None,
        last_worker_error: str | None = None,
    ) -> dict[str, Any] | None:
        worker_status_value = worker_status
        if worker_status_value is None:
            worker_status_value = "retry_scheduled" if status == "queued" else "completed"
        rowcounts = self._write_with_rowcounts(
            [
                (
                    UPDATE_STAFF_INVITE_DELIVERY_ATTEMPT_STATUS_SQL,
                    {
                        "attempt_id": attempt_id,
                        "status": status,
                        "error": error,
                        "worker_status": worker_status_value,
                        "next_worker_run_at": next_worker_run_at,
                        "dead_letter_at": dead_letter_at,
                        "last_worker_error": last_worker_error,
                    },
                )
            ]
        )
        if not rowcounts or rowcounts[0] == 0:
            return None
        return self.get_staff_invite_delivery_attempt(attempt_id)

    def update_staff_invite_delivery_worker_state(
        self,
        attempt_id: str,
        *,
        status: str,
        error: str | None,
        worker_status: str,
        worker_attempt_count: int,
        next_worker_run_at: str | None,
        dead_letter_at: str | None,
        last_worker_error: str | None,
    ) -> dict[str, Any] | None:
        rowcounts = self._write_with_rowcounts(
            [
                (
                    UPDATE_STAFF_INVITE_DELIVERY_WORKER_STATE_SQL,
                    {
                        "attempt_id": attempt_id,
                        "status": status,
                        "error": error,
                        "worker_status": worker_status,
                        "worker_attempt_count": worker_attempt_count,
                        "next_worker_run_at": next_worker_run_at,
                        "dead_letter_at": dead_letter_at,
                        "last_worker_error": last_worker_error,
                    },
                )
            ]
        )
        if not rowcounts or rowcounts[0] == 0:
            return None
        return self.get_staff_invite_delivery_attempt(attempt_id)

    def list_staff_invite_delivery_outbox_attempts(self) -> list[dict[str, Any]]:
        return [
            postgres_staff_invite_delivery_outbox_attempt_from_row(row)
            for row in self._fetchall(LIST_STAFF_INVITE_DELIVERY_OUTBOX_ATTEMPTS_SQL)
        ]

    def record_staff_invite_delivery_event(
        self,
        *,
        event_id: str,
        provider: str,
        provider_event_id: str,
        attempt_id: str,
        token: str,
        event_type: str,
        mapped_attempt_status: str,
        occurred_at: str | None,
        recipient: str | None,
        error: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self._fetchone(
            GET_STAFF_INVITE_DELIVERY_EVENT_ID_BY_PROVIDER_SQL,
            {
                "provider": provider,
                "provider_event_id": provider_event_id,
            },
        )
        if existing is None:
            self._write(
                [
                    (
                        RECORD_STAFF_INVITE_DELIVERY_EVENT_SQL,
                        {
                            "event_id": event_id,
                            "provider": provider,
                            "provider_event_id": provider_event_id,
                            "attempt_id": attempt_id,
                            "token": token,
                            "event_type": event_type,
                            "mapped_attempt_status": mapped_attempt_status,
                            "received_at": _now_iso(),
                            "occurred_at": occurred_at,
                            "recipient": recipient,
                            "error": error,
                            "metadata_json": _json_dumps(metadata),
                        },
                    )
                ]
            )
            stored_event_id = event_id
            was_duplicate = False
        else:
            stored_event_id = _row_to_mapping(existing, ("event_id",))["event_id"]
            was_duplicate = True
        event = self.get_staff_invite_delivery_event(str(stored_event_id)) or {}
        event["was_duplicate"] = was_duplicate
        return event

    def get_staff_invite_delivery_event(
        self,
        event_id: str,
    ) -> dict[str, Any] | None:
        row = self._fetchone(
            GET_STAFF_INVITE_DELIVERY_EVENT_SQL,
            {"event_id": event_id},
        )
        return postgres_staff_invite_delivery_event_from_row(row) if row else None

    def list_staff_invite_delivery_events(
        self,
        token: str,
    ) -> list[dict[str, Any]]:
        events = [
            postgres_staff_invite_delivery_event_from_row(row)
            for row in self._fetchall(
                LIST_STAFF_INVITE_DELIVERY_EVENTS_SQL,
                {"token": token},
            )
        ]
        for event in events:
            event["was_duplicate"] = False
        return events

    def create_application(
        self,
        *,
        application_id: str,
        borrower_email: str,
        requested_amount: float,
        purpose: str,
        district: str | None,
        settlement_type: str | None,
        behavioral_signals: dict[str, Any],
        consent_version: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        self._write(
            [
                (
                    CREATE_APPLICATION_SQL,
                    {
                        "application_id": application_id,
                        "borrower_email": borrower_email,
                        "requested_amount": requested_amount,
                        "purpose": purpose,
                        "district": district,
                        "settlement_type": settlement_type,
                        "organization_id": organization_id,
                        "behavioral_signals_json": _json_dumps(behavioral_signals),
                        "created_at": _now_iso(),
                    },
                )
            ]
        )
        self.record_audit_event(
            actor_email=borrower_email,
            action="application_created",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "requested_amount": requested_amount,
                "consent_confirmed": consent_version is not None,
                "consent_version": consent_version,
                "organization_id": organization_id,
            },
        )
        return self.get_application(application_id) or {}

    def _latest_application_decision(
        self,
        application_id: str,
    ) -> dict[str, Any] | None:
        row = self._fetchone(
            GET_LATEST_APPLICATION_DECISION_SQL,
            {"application_id": application_id},
        )
        return postgres_application_decision_from_row(row) if row else None

    def _application_from_row(self, row: object) -> dict[str, Any]:
        application = postgres_application_from_row(row)
        application["decision_result"] = self._latest_application_decision(
            str(application["id"])
        )
        return application

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            GET_APPLICATION_SQL,
            {"application_id": application_id},
        )
        return self._application_from_row(row) if row else None

    def list_applications(
        self,
        organization_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if organization_id is None:
            rows = self._fetchall(LIST_APPLICATIONS_SQL)
        else:
            rows = self._fetchall(
                LIST_APPLICATIONS_BY_ORGANIZATION_SQL,
                {"organization_id": organization_id},
            )
        return [self._application_from_row(row) for row in rows]

    def list_borrower_applications(
        self,
        borrower_email: str,
    ) -> list[dict[str, Any]]:
        return [
            self._application_from_row(row)
            for row in self._fetchall(
                LIST_BORROWER_APPLICATIONS_SQL,
                {"borrower_email": borrower_email},
            )
        ]

    def assign_application_organization(
        self,
        application_id: str,
        organization_id: str,
    ) -> None:
        self._write(
            [
                (
                    ASSIGN_APPLICATION_ORGANIZATION_SQL,
                    {
                        "application_id": application_id,
                        "organization_id": organization_id,
                    },
                )
            ]
        )

    def clear_applications(self, *, actor_email: str) -> int:
        row = self._fetchone(COUNT_APPLICATIONS_SQL)
        deleted_count = int(_row_to_mapping(row, ("count",)).get("count") or 0)
        self._write([(DELETE_APPLICATIONS_SQL, {})])
        self.record_audit_event(
            actor_email=actor_email,
            action="applications_cleared",
            entity_type="loan_application",
            entity_id=None,
            details={"deleted_count": deleted_count},
        )
        return deleted_count

    def update_application_score(
        self,
        *,
        application_id: str,
        score_result: dict[str, Any],
        actor_email: str,
    ) -> dict[str, Any] | None:
        current = self._fetchone(
            GET_APPLICATION_SCORE_STATE_SQL,
            {"application_id": application_id},
        )
        if current is None:
            return None
        current_state = _row_to_mapping(current, ("status", "score_result_json"))
        previous_status = str(current_state["status"])
        if previous_status in TERMINAL_APPLICATION_STATUSES:
            raise InvalidApplicationTransitionError(
                f"Cannot score an application after it is {previous_status}"
            )
        next_status = "scored" if previous_status == "submitted" else previous_status
        action = (
            "application_scored"
            if current_state["score_result_json"] is None
            else "application_rescored"
        )
        self._write(
            [
                (
                    UPDATE_APPLICATION_SCORE_SQL,
                    {
                        "application_id": application_id,
                        "status": next_status,
                        "score_result_json": _json_dumps(score_result),
                        "scored_at": _now_iso(),
                    },
                )
            ]
        )
        self.record_audit_event(
            actor_email=actor_email,
            action=action,
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "model_version": score_result.get("model_version"),
                "risk_band": score_result.get("risk_band"),
                "previous_status": previous_status,
                "status": next_status,
            },
        )
        return self.get_application(application_id)

    def record_application_decision(
        self,
        *,
        application_id: str,
        actor_email: str,
        decision: str,
        policy_name: str | None,
        note: str,
    ) -> dict[str, Any] | None:
        current = self._fetchone(
            GET_APPLICATION_SCORE_STATE_SQL,
            {"application_id": application_id},
        )
        if current is None:
            return None
        current_state = _row_to_mapping(current, ("status", "score_result_json"))
        previous_status = str(current_state["status"])
        if current_state["score_result_json"] is None:
            raise InvalidApplicationTransitionError(
                "Score the application before recording an MFI decision"
            )
        if decision not in DECISION_TRANSITIONS.get(previous_status, set()):
            raise InvalidApplicationTransitionError(
                f"Cannot record {decision} while application status is {previous_status}"
            )
        next_status = DECISION_WORKFLOW_STATUSES[decision]
        self._write(
            [
                (
                    RECORD_APPLICATION_DECISION_SQL,
                    {
                        "application_id": application_id,
                        "actor_email": actor_email,
                        "decision": decision,
                        "policy_name": policy_name,
                        "note": note,
                        "created_at": _now_iso(),
                    },
                ),
                (
                    UPDATE_APPLICATION_STATUS_SQL,
                    {
                        "application_id": application_id,
                        "status": next_status,
                    },
                ),
            ]
        )
        self.record_audit_event(
            actor_email=actor_email,
            action="application_decision_recorded",
            entity_type="loan_application",
            entity_id=application_id,
            details={
                "decision": decision,
                "policy_name": policy_name,
                "previous_status": previous_status,
                "status": next_status,
            },
        )
        return self.get_application(application_id)

    def list_application_decisions(
        self,
        application_id: str,
    ) -> list[dict[str, Any]]:
        return [
            postgres_application_decision_from_row(row)
            for row in self._fetchall(
                LIST_APPLICATION_DECISIONS_SQL,
                {"application_id": application_id},
            )
        ]

    def list_application_timeline(
        self,
        application_id: str,
    ) -> list[dict[str, Any]]:
        return [
            postgres_audit_event_from_row(row)
            for row in self._fetchall(
                LIST_APPLICATION_TIMELINE_SQL,
                {"application_id": application_id},
            )
        ]


@dataclass(frozen=True)
class PostgresRepositoryAdapterSkeleton:
    """Runtime guardrail that keeps backend selection disabled."""

    database_url_env: str = "MICROSCORE_DATABASE_URL"
    runtime_enabled: bool = False

    @property
    def backend(self) -> str:
        return "postgresql"

    def describe_contract(self) -> dict[str, object]:
        return {
            **repository_contract_summary(),
            "backend": self.backend,
            "database_url_env": self.database_url_env,
        }

    def connect(self) -> NoReturn:
        raise RuntimeError(
            "PostgreSQL repository adapter runtime is disabled. "
            "Use PostgresRepositoryAdapter with an injected connection_factory "
            "only in parity tests until production storage controls are implemented."
        )
