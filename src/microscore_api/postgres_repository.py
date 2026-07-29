"""Contract-only PostgreSQL repository adapter skeleton.

This module is deliberately not a live backend. It records the repository method
families that a future PostgreSQL implementation must support before
``MICROSCORE_STORAGE_BACKEND=postgresql`` can be enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn


POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION = "postgresql-repository-adapter-v1"
POSTGRESQL_REPOSITORY_ADAPTER_MODULE = "microscore_api.postgres_repository"
POSTGRESQL_REPOSITORY_ADAPTER_STATUS = "contract_only"
POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION = (
    "PostgreSQL Repository Adapter Skeleton v1 defines method families and "
    "runtime guardrails only. It does not open PostgreSQL connections, does not "
    "execute repository queries, and does not make storage production-ready."
)


@dataclass(frozen=True)
class RepositoryMethodGroup:
    key: str
    label: str
    methods: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "method_count": len(self.methods),
            "methods": list(self.methods),
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


def repository_contract_summary() -> dict[str, object]:
    methods = repository_contract_methods()
    return {
        "module": POSTGRESQL_REPOSITORY_ADAPTER_MODULE,
        "version": POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT_VERSION,
        "status": POSTGRESQL_REPOSITORY_ADAPTER_STATUS,
        "present": True,
        "runtime_enabled": False,
        "method_count": len(methods),
        "method_groups": [group.as_dict() for group in REPOSITORY_METHOD_GROUPS],
        "limitation": POSTGRESQL_REPOSITORY_ADAPTER_LIMITATION,
    }


@dataclass(frozen=True)
class PostgresRepositoryAdapterSkeleton:
    """Non-executable adapter placeholder for future PostgreSQL implementation."""

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
            "PostgreSQL repository adapter is contract-only. "
            "Do not call connect() until repository parity tests and production "
            "storage controls are implemented."
        )
