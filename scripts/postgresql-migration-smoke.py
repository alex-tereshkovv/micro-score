from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from microscore_api.database import (  # noqa: E402
    JSON_TEXT_COLUMNS,
    POSTGRESQL_TENANT_SCOPE_INDEXES,
    REQUIRED_SCHEMA_TABLES,
)
from microscore_api.postgres_repository import (  # noqa: E402
    POSTGRESQL_APPLICATION_LIFECYCLE_METHODS,
    POSTGRESQL_AUDIT_METHODS,
    POSTGRESQL_IDENTITY_METHODS,
    POSTGRESQL_MODEL_REGISTRY_METHODS,
    POSTGRESQL_MODEL_REGISTRY_READ_METHODS,
    POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS,
    POSTGRESQL_ORGANIZATION_METHODS,
    POSTGRESQL_PORTFOLIO_ANALYTICS_METHODS,
    POSTGRESQL_STAFF_INVITE_METHODS,
)


DEFAULT_MIGRATION_PATH = (
    PROJECT_ROOT / "migrations" / "postgresql" / "0001_initial_schema.sql"
)
SCHEMA_MIGRATION_VERSION = "0001_initial_schema"
EXPECTED_TABLES = (*REQUIRED_SCHEMA_TABLES, "schema_migrations")


def _load_migration(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Migration file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def validate_migration_text(path: Path) -> dict[str, object]:
    sql = _load_migration(path)
    missing_tables = [
        table
        for table in EXPECTED_TABLES
        if f"CREATE TABLE IF NOT EXISTS {table}" not in sql
    ]
    missing_jsonb_columns = [
        item
        for item in JSON_TEXT_COLUMNS
        if f"{item.split('.', 1)[1]} JSONB" not in sql
    ]
    missing_tenant_indexes = [
        index_name
        for index_name in POSTGRESQL_TENANT_SCOPE_INDEXES
        if f"CREATE INDEX IF NOT EXISTS {index_name}" not in sql
    ]
    if SCHEMA_MIGRATION_VERSION not in sql:
        raise RuntimeError(f"{SCHEMA_MIGRATION_VERSION} is not recorded in migration SQL")
    if missing_tables or missing_jsonb_columns or missing_tenant_indexes:
        raise RuntimeError(
            "PostgreSQL migration draft is incomplete: "
            + json.dumps(
                {
                    "missing_tables": missing_tables,
                    "missing_jsonb_columns": missing_jsonb_columns,
                    "missing_tenant_indexes": missing_tenant_indexes,
                },
                sort_keys=True,
            )
        )
    return {
        "migration": path.relative_to(PROJECT_ROOT).as_posix(),
        "version": SCHEMA_MIGRATION_VERSION,
        "expected_tables": len(EXPECTED_TABLES),
        "expected_jsonb_columns": len(JSON_TEXT_COLUMNS),
        "expected_tenant_indexes": len(POSTGRESQL_TENANT_SCOPE_INDEXES),
        "expected_model_registry_read_methods": len(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "expected_model_registry_write_methods": len(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS),
        "expected_model_registry_methods": len(POSTGRESQL_MODEL_REGISTRY_METHODS),
        "expected_audit_methods": len(POSTGRESQL_AUDIT_METHODS),
        "expected_organization_methods": len(POSTGRESQL_ORGANIZATION_METHODS),
        "expected_identity_methods": len(POSTGRESQL_IDENTITY_METHODS),
        "expected_staff_invite_methods": len(POSTGRESQL_STAFF_INVITE_METHODS),
        "expected_application_lifecycle_methods": len(
            POSTGRESQL_APPLICATION_LIFECYCLE_METHODS
        ),
        "expected_portfolio_analytics_methods": len(
            POSTGRESQL_PORTFOLIO_ANALYTICS_METHODS
        ),
    }


def run_psql(
    *,
    psql_bin: str,
    database_url: str,
    arguments: Sequence[str],
) -> str:
    command = [
        psql_bin,
        "--no-psqlrc",
        "--set",
        "ON_ERROR_STOP=1",
        "--dbname",
        database_url,
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            "psql failed with exit code "
            f"{exc.returncode}. stdout={stdout!r} stderr={stderr!r}"
        ) from None
    return completed.stdout.strip()


def query_rows(*, psql_bin: str, database_url: str, sql: str) -> list[str]:
    output = run_psql(
        psql_bin=psql_bin,
        database_url=database_url,
        arguments=[
            "--tuples-only",
            "--no-align",
            "--field-separator",
            "\t",
            "--command",
            sql,
        ],
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def assert_catalog_subset(
    *,
    expected: Sequence[str],
    actual: Sequence[str],
    label: str,
) -> None:
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise RuntimeError(f"Missing PostgreSQL {label}: {', '.join(missing)}")


def apply_migration_and_verify(
    *,
    migration_path: Path,
    database_url: str,
    psql_bin: str,
) -> dict[str, object]:
    if not database_url:
        raise RuntimeError("MICROSCORE_DATABASE_URL is required for live PostgreSQL smoke")
    if shutil.which(psql_bin) is None:
        raise RuntimeError(f"psql binary was not found: {psql_bin}")

    run_psql(
        psql_bin=psql_bin,
        database_url=database_url,
        arguments=["--file", str(migration_path)],
    )
    run_psql(
        psql_bin=psql_bin,
        database_url=database_url,
        arguments=[
            "--command",
            """
            INSERT INTO mfi_organizations (id, name, region, created_at)
            VALUES ('ci-smoke-mfi', 'CI Smoke MFI', 'Pavlodar', NOW())
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

            INSERT INTO users (email, password_hash, role, organization_id, created_at)
            VALUES
                ('ci-smoke-admin@example.com', 'hash', 'admin', NULL, NOW()),
                ('ci-smoke-borrower@example.com', 'hash', 'borrower', NULL, NOW()),
                ('ci-smoke-analyst@example.com', 'hash', 'mfi_analyst', 'ci-smoke-mfi', NOW()),
                ('ci-smoke-disabled@example.com', 'hash', 'mfi_analyst', 'ci-smoke-mfi', NOW())
            ON CONFLICT (email) DO UPDATE
            SET
                role = EXCLUDED.role,
                organization_id = EXCLUDED.organization_id;

            UPDATE users
            SET organization_id = 'ci-smoke-mfi'
            WHERE email = 'ci-smoke-analyst@example.com';

            UPDATE users
            SET
                mfa_attested_at = NOW(),
                mfa_attested_by = 'ci-smoke-admin@example.com',
                mfa_method = 'totp'
            WHERE email = 'ci-smoke-analyst@example.com';

            INSERT INTO sessions (token, email, created_at)
            VALUES
                ('ci-smoke-active-session', 'ci-smoke-analyst@example.com', NOW()),
                ('ci-smoke-revoked-session', 'ci-smoke-disabled@example.com', NOW())
            ON CONFLICT (token) DO UPDATE
            SET
                email = EXCLUDED.email,
                created_at = EXCLUDED.created_at;

            UPDATE users
            SET
                disabled_at = NOW(),
                disabled_by = 'ci-smoke-admin@example.com'
            WHERE email = 'ci-smoke-disabled@example.com';

            DELETE FROM sessions
            WHERE token = 'ci-smoke-revoked-session';

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
                'ci-smoke-invite',
                'ci-smoke-invitee@example.com',
                'mfi_analyst',
                'ci-smoke-mfi',
                'ci-smoke-admin@example.com',
                NOW(),
                NOW() + INTERVAL '2 days'
            )
            ON CONFLICT (token) DO UPDATE
            SET
                email = EXCLUDED.email,
                role = EXCLUDED.role,
                organization_id = EXCLUDED.organization_id,
                created_by = EXCLUDED.created_by,
                expires_at = EXCLUDED.expires_at,
                accepted_at = NULL,
                accepted_by = NULL,
                revoked_at = NULL,
                revoked_by = NULL,
                delivered_at = NULL,
                delivered_by = NULL,
                delivery_channel = NULL,
                delivery_recipient = NULL,
                delivery_url_base = NULL,
                delivery_note = NULL;

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
                'ci-smoke-invite-attempt',
                'ci-smoke-invite',
                NOW(),
                'ci-smoke-admin@example.com',
                'local_outbox',
                'queued',
                'email',
                'ci-smoke-invitee@example.com',
                'https://example.test/invites',
                'postgresql migration smoke',
                NULL,
                'queued',
                0,
                NOW(),
                NULL,
                NULL
            )
            ON CONFLICT (attempt_id) DO UPDATE
            SET
                status = EXCLUDED.status,
                worker_status = EXCLUDED.worker_status,
                worker_attempt_count = EXCLUDED.worker_attempt_count,
                next_worker_run_at = EXCLUDED.next_worker_run_at,
                dead_letter_at = NULL,
                last_worker_error = NULL;

            UPDATE staff_invite_delivery_attempts
            SET
                status = 'sent',
                error = NULL,
                worker_status = 'completed',
                worker_attempt_count = 1,
                next_worker_run_at = NULL,
                dead_letter_at = NULL,
                last_worker_error = NULL
            WHERE attempt_id = 'ci-smoke-invite-attempt';

            UPDATE staff_invites
            SET
                delivered_at = NOW(),
                delivered_by = 'ci-smoke-admin@example.com',
                delivery_channel = 'email',
                delivery_recipient = 'ci-smoke-invitee@example.com',
                delivery_url_base = 'https://example.test/invites',
                delivery_note = 'postgresql migration smoke'
            WHERE token = 'ci-smoke-invite' AND delivered_at IS NULL;

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
                'ci-smoke-invite-event',
                'local_outbox',
                'ci-smoke-provider-event',
                'ci-smoke-invite-attempt',
                'ci-smoke-invite',
                'delivered',
                'delivered',
                NOW(),
                NOW(),
                'ci-smoke-invitee@example.com',
                NULL,
                '{"message_id": "ci-smoke-message"}'::jsonb
            )
            ON CONFLICT (event_id) DO UPDATE
            SET
                event_type = EXCLUDED.event_type,
                mapped_attempt_status = EXCLUDED.mapped_attempt_status,
                metadata_json = EXCLUDED.metadata_json;

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
                'ci-smoke-application',
                'ci-smoke-borrower@example.com',
                'scored',
                125000.00,
                'postgresql migration smoke',
                'Pavlodar city',
                'urban',
                'ci-smoke-mfi',
                '{"mobile_logins": 4, "late_payment_count": 0}'::jsonb,
                '{"risk_band": "low", "score": 0.82}'::jsonb,
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO UPDATE
            SET
                borrower_email = EXCLUDED.borrower_email,
                status = EXCLUDED.status,
                requested_amount = EXCLUDED.requested_amount,
                purpose = EXCLUDED.purpose,
                district = EXCLUDED.district,
                settlement_type = EXCLUDED.settlement_type,
                organization_id = EXCLUDED.organization_id,
                behavioral_signals_json = EXCLUDED.behavioral_signals_json,
                score_result_json = EXCLUDED.score_result_json,
                scored_at = EXCLUDED.scored_at;

            DELETE FROM application_decisions
            WHERE application_id = 'ci-smoke-application';

            INSERT INTO application_decisions (
                application_id,
                actor_email,
                decision,
                policy_name,
                note,
                created_at
            )
            VALUES (
                'ci-smoke-application',
                'ci-smoke-analyst@example.com',
                'review',
                'ci-smoke-policy',
                'migration smoke manual review',
                NOW()
            );

            UPDATE loan_applications
            SET status = 'under_review'
            WHERE id = 'ci-smoke-application';

            INSERT INTO application_decisions (
                application_id,
                actor_email,
                decision,
                policy_name,
                note,
                created_at
            )
            VALUES (
                'ci-smoke-application',
                'ci-smoke-analyst@example.com',
                'approve',
                'ci-smoke-policy',
                'migration smoke approval',
                NOW()
            );

            UPDATE loan_applications
            SET status = 'approved'
            WHERE id = 'ci-smoke-application';

            INSERT INTO audit_events (
                actor_email,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES
                (
                    'ci-smoke-borrower@example.com',
                    'application_created',
                    'loan_application',
                    'ci-smoke-application',
                    '{"method_group": "application_lifecycle", "status": "submitted"}'::jsonb,
                    NOW()
                ),
                (
                    'ci-smoke-analyst@example.com',
                    'application_scored',
                    'loan_application',
                    'ci-smoke-application',
                    '{"method_group": "application_lifecycle", "status": "scored"}'::jsonb,
                    NOW()
                ),
                (
                    'ci-smoke-analyst@example.com',
                    'application_decision_recorded',
                    'loan_application',
                    'ci-smoke-application',
                    '{"method_group": "application_lifecycle", "decision": "approve"}'::jsonb,
                    NOW()
                );

            INSERT INTO portfolio_simulations (
                id,
                organization_id,
                actor_email,
                portfolio_fingerprint,
                request_json,
                result_json,
                created_at
            )
            VALUES (
                'ci-smoke-simulation',
                'ci-smoke-mfi',
                'ci-smoke-analyst@example.com',
                'ci-smoke-portfolio-fingerprint',
                '{"iterations": 500, "seed": 991, "scenarios": ["baseline", "adverse", "severe"]}'::jsonb,
                '{"scenario_results": [{"scenario": "baseline"}, {"scenario": "adverse"}, {"scenario": "severe"}], "warnings": ["postgresql migration smoke"]}'::jsonb,
                NOW()
            )
            ON CONFLICT (id) DO UPDATE
            SET
                organization_id = EXCLUDED.organization_id,
                actor_email = EXCLUDED.actor_email,
                portfolio_fingerprint = EXCLUDED.portfolio_fingerprint,
                request_json = EXCLUDED.request_json,
                result_json = EXCLUDED.result_json,
                created_at = EXCLUDED.created_at;

            UPDATE model_versions
            SET lifecycle_status = 'inactive', is_active = FALSE
            WHERE version IN ('ci-smoke-model', 'ci-smoke-model-candidate');

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
                'ci-smoke-model',
                'CI Smoke Model',
                'logistic_regression',
                'inactive',
                FALSE,
                'behavioral-v1',
                'ci-smoke',
                42,
                '{"roc_auc": 0.81}'::jsonb,
                '["disposable CI smoke only"]'::jsonb,
                'ci',
                NOW(),
                NOW()
            )
            ON CONFLICT (version) DO UPDATE
            SET
                lifecycle_status = EXCLUDED.lifecycle_status,
                is_active = EXCLUDED.is_active,
                metrics_json = EXCLUDED.metrics_json,
                activated_at = EXCLUDED.activated_at;

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
                'ci-smoke-model-candidate',
                'CI Smoke Candidate Model',
                'logistic_regression',
                'candidate',
                FALSE,
                'behavioral-v2',
                'ci-smoke-candidate',
                43,
                '{"roc_auc": 0.84}'::jsonb,
                '["disposable CI write smoke only"]'::jsonb,
                'ci',
                NOW(),
                NULL
            )
            ON CONFLICT (version) DO UPDATE
            SET
                lifecycle_status = EXCLUDED.lifecycle_status,
                is_active = EXCLUDED.is_active,
                metrics_json = EXCLUDED.metrics_json,
                activated_at = EXCLUDED.activated_at;

            UPDATE model_versions
            SET lifecycle_status = 'inactive', is_active = FALSE
            WHERE is_active IS TRUE AND version <> 'ci-smoke-model-candidate';

            UPDATE model_versions
            SET lifecycle_status = 'active', is_active = TRUE, activated_at = NOW()
            WHERE version = 'ci-smoke-model-candidate';

            INSERT INTO audit_events (
                actor_email,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES (
                'ci-smoke-analyst@example.com',
                'postgresql_audit_adapter_smoke',
                'postgres_repository',
                'audit',
                '{"method_group": "audit", "complete": true}'::jsonb,
                NOW()
            );
            """,
        ],
    )

    tables = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """,
    )
    jsonb_columns = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT table_name || '.' || column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND data_type = 'jsonb'
            ORDER BY 1;
        """,
    )
    indexes = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY indexname;
        """,
    )
    schema_version = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT version
            FROM schema_migrations
            WHERE version = '0001_initial_schema';
        """,
    )
    jsonb_value = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT score_result_json->>'risk_band'
            FROM loan_applications
            WHERE id = 'ci-smoke-application';
        """,
    )
    application_lifecycle_status = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT status || ':' || (score_result_json->>'risk_band')
            FROM loan_applications
            WHERE id = 'ci-smoke-application';
        """,
    )
    application_decision_count = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT COUNT(*)::text
            FROM application_decisions
            WHERE application_id = 'ci-smoke-application';
        """,
    )
    application_latest_decision = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT decision || ':' || COALESCE(policy_name, '')
            FROM application_decisions
            WHERE application_id = 'ci-smoke-application'
            ORDER BY id DESC
            LIMIT 1;
        """,
    )
    application_timeline_latest_action = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT action
            FROM audit_events
            WHERE entity_type = 'loan_application'
                AND entity_id = 'ci-smoke-application'
            ORDER BY id DESC
            LIMIT 1;
        """,
    )
    portfolio_simulation_jsonb = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT
                organization_id
                || ':' || (request_json->>'seed')
                || ':' || jsonb_array_length(result_json->'scenario_results')::text
            FROM portfolio_simulations
            WHERE id = 'ci-smoke-simulation';
        """,
    )
    portfolio_simulation_scope_count = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT COUNT(*)::text
            FROM portfolio_simulations
            WHERE organization_id = 'ci-smoke-mfi';
        """,
    )
    active_model_version = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT version
            FROM model_versions
            WHERE is_active IS TRUE
            ORDER BY activated_at DESC NULLS LAST, created_at DESC, version DESC
            LIMIT 1;
        """,
    )
    active_model_metric = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT metrics_json->>'roc_auc'
            FROM model_versions
            WHERE version = 'ci-smoke-model-candidate';
        """,
    )
    active_model_status = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT lifecycle_status || ':' || is_active::text
            FROM model_versions
            WHERE version = 'ci-smoke-model-candidate';
        """,
    )
    organization_directory = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT id || ':' || name
            FROM mfi_organizations
            WHERE id = 'ci-smoke-mfi';
        """,
    )
    organization_assignment = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT organization_id
            FROM users
            WHERE email = 'ci-smoke-analyst@example.com';
        """,
    )
    identity_mfa_method = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT mfa_method
            FROM users
            WHERE email = 'ci-smoke-analyst@example.com';
        """,
    )
    identity_session_scope = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT users.role || ':' || COALESCE(users.organization_id, '')
            FROM sessions
            JOIN users ON users.email = sessions.email
            WHERE sessions.token = 'ci-smoke-active-session';
        """,
    )
    identity_disabled_by = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT disabled_by
            FROM users
            WHERE email = 'ci-smoke-disabled@example.com';
        """,
    )
    identity_revoked_session_count = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT COUNT(*)::text
            FROM sessions
            WHERE token = 'ci-smoke-revoked-session';
        """,
    )
    staff_invite_delivery = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT delivery_channel || ':' || delivery_recipient
            FROM staff_invites
            WHERE token = 'ci-smoke-invite';
        """,
    )
    staff_invite_attempt_status = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT status || ':' || worker_status || ':' || worker_attempt_count::text
            FROM staff_invite_delivery_attempts
            WHERE attempt_id = 'ci-smoke-invite-attempt';
        """,
    )
    staff_invite_event_metadata = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT event_type || ':' || (metadata_json->>'message_id')
            FROM staff_invite_delivery_events
            WHERE event_id = 'ci-smoke-invite-event';
        """,
    )
    latest_audit_action = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT action
            FROM audit_events
            ORDER BY id DESC
            LIMIT 1;
        """,
    )
    latest_audit_detail = query_rows(
        psql_bin=psql_bin,
        database_url=database_url,
        sql="""
            SELECT details_json->>'method_group'
            FROM audit_events
            WHERE action = 'postgresql_audit_adapter_smoke'
            ORDER BY id DESC
            LIMIT 1;
        """,
    )

    assert_catalog_subset(expected=EXPECTED_TABLES, actual=tables, label="tables")
    assert_catalog_subset(
        expected=JSON_TEXT_COLUMNS,
        actual=jsonb_columns,
        label="jsonb columns",
    )
    assert_catalog_subset(
        expected=POSTGRESQL_TENANT_SCOPE_INDEXES,
        actual=indexes,
        label="tenant-scope indexes",
    )
    assert_catalog_subset(
        expected=[SCHEMA_MIGRATION_VERSION],
        actual=schema_version,
        label="schema migration version",
    )
    assert_catalog_subset(expected=["low"], actual=jsonb_value, label="JSONB smoke row")
    assert_catalog_subset(
        expected=["approved:low"],
        actual=application_lifecycle_status,
        label="application lifecycle status",
    )
    assert_catalog_subset(
        expected=["2"],
        actual=application_decision_count,
        label="application decision count",
    )
    assert_catalog_subset(
        expected=["approve:ci-smoke-policy"],
        actual=application_latest_decision,
        label="application latest decision",
    )
    assert_catalog_subset(
        expected=["application_decision_recorded"],
        actual=application_timeline_latest_action,
        label="application timeline latest action",
    )
    assert_catalog_subset(
        expected=["ci-smoke-mfi:991:3"],
        actual=portfolio_simulation_jsonb,
        label="portfolio simulation JSONB row",
    )
    assert_catalog_subset(
        expected=["1"],
        actual=portfolio_simulation_scope_count,
        label="portfolio simulation organization scope",
    )
    assert_catalog_subset(
        expected=["ci-smoke-model-candidate"],
        actual=active_model_version,
        label="active model registry row",
    )
    assert_catalog_subset(
        expected=["0.84"],
        actual=active_model_metric,
        label="model registry JSONB metric",
    )
    assert_catalog_subset(
        expected=["active:true"],
        actual=active_model_status,
        label="model registry activation status",
    )
    assert_catalog_subset(
        expected=["ci-smoke-mfi:CI Smoke MFI"],
        actual=organization_directory,
        label="organization directory row",
    )
    assert_catalog_subset(
        expected=["ci-smoke-mfi"],
        actual=organization_assignment,
        label="organization user assignment",
    )
    assert_catalog_subset(
        expected=["totp"],
        actual=identity_mfa_method,
        label="identity MFA method",
    )
    assert_catalog_subset(
        expected=["mfi_analyst:ci-smoke-mfi"],
        actual=identity_session_scope,
        label="identity active session scope",
    )
    assert_catalog_subset(
        expected=["ci-smoke-admin@example.com"],
        actual=identity_disabled_by,
        label="identity disable actor",
    )
    assert_catalog_subset(
        expected=["0"],
        actual=identity_revoked_session_count,
        label="identity revoked session count",
    )
    assert_catalog_subset(
        expected=["email:ci-smoke-invitee@example.com"],
        actual=staff_invite_delivery,
        label="staff invite delivery marker",
    )
    assert_catalog_subset(
        expected=["sent:completed:1"],
        actual=staff_invite_attempt_status,
        label="staff invite delivery attempt worker state",
    )
    assert_catalog_subset(
        expected=["delivered:ci-smoke-message"],
        actual=staff_invite_event_metadata,
        label="staff invite delivery event metadata",
    )
    assert_catalog_subset(
        expected=["postgresql_audit_adapter_smoke"],
        actual=latest_audit_action,
        label="latest audit action",
    )
    assert_catalog_subset(
        expected=["audit"],
        actual=latest_audit_detail,
        label="audit JSONB details",
    )

    return {
        "migration": migration_path.relative_to(PROJECT_ROOT).as_posix(),
        "version": SCHEMA_MIGRATION_VERSION,
        "tables": len(tables),
        "required_tables": len(EXPECTED_TABLES),
        "jsonb_columns": len(jsonb_columns),
        "required_jsonb_columns": len(JSON_TEXT_COLUMNS),
        "tenant_indexes": len(
            set(indexes).intersection(POSTGRESQL_TENANT_SCOPE_INDEXES)
        ),
        "required_tenant_indexes": len(POSTGRESQL_TENANT_SCOPE_INDEXES),
        "jsonb_smoke_row": jsonb_value[0],
        "model_registry_active_version": active_model_version[0],
        "model_registry_metric_roc_auc": active_model_metric[0],
        "model_registry_read_methods": len(POSTGRESQL_MODEL_REGISTRY_READ_METHODS),
        "model_registry_write_methods": len(POSTGRESQL_MODEL_REGISTRY_WRITE_METHODS),
        "model_registry_methods": len(POSTGRESQL_MODEL_REGISTRY_METHODS),
        "audit_methods": len(POSTGRESQL_AUDIT_METHODS),
        "organization_methods": len(POSTGRESQL_ORGANIZATION_METHODS),
        "identity_methods": len(POSTGRESQL_IDENTITY_METHODS),
        "staff_invite_methods": len(POSTGRESQL_STAFF_INVITE_METHODS),
        "application_lifecycle_methods": len(POSTGRESQL_APPLICATION_LIFECYCLE_METHODS),
        "application_lifecycle_status": application_lifecycle_status[0],
        "application_decision_count": application_decision_count[0],
        "application_latest_decision": application_latest_decision[0],
        "application_timeline_latest_action": application_timeline_latest_action[0],
        "portfolio_analytics_methods": len(POSTGRESQL_PORTFOLIO_ANALYTICS_METHODS),
        "portfolio_simulation_jsonb": portfolio_simulation_jsonb[0],
        "portfolio_simulation_scope_count": portfolio_simulation_scope_count[0],
        "organization_directory": organization_directory[0],
        "organization_assignment": organization_assignment[0],
        "identity_mfa_method": identity_mfa_method[0],
        "identity_session_scope": identity_session_scope[0],
        "identity_disabled_by": identity_disabled_by[0],
        "identity_revoked_session_count": identity_revoked_session_count[0],
        "staff_invite_delivery": staff_invite_delivery[0],
        "staff_invite_attempt_status": staff_invite_attempt_status[0],
        "staff_invite_event_metadata": staff_invite_event_metadata[0],
        "audit_latest_action": latest_audit_action[0],
        "audit_detail_method_group": latest_audit_detail[0],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply and verify the MicroScore PostgreSQL migration draft.",
    )
    parser.add_argument(
        "--migration",
        type=Path,
        default=DEFAULT_MIGRATION_PATH,
        help="Path to the PostgreSQL migration SQL file.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("MICROSCORE_DATABASE_URL", ""),
        help="PostgreSQL connection URL. Defaults to MICROSCORE_DATABASE_URL.",
    )
    parser.add_argument(
        "--psql-bin",
        default=os.environ.get("PSQL_BIN", "psql"),
        help="psql executable name or path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate migration text only; do not connect to PostgreSQL.",
    )
    return parser.parse_args()


def main() -> None:
    try:
        args = parse_args()
        migration_path = args.migration.resolve()
        text_summary = validate_migration_text(migration_path)
        if args.dry_run:
            result = {"mode": "postgresql-migration-smoke-dry-run", **text_summary}
        else:
            result = {
                "mode": "postgresql-migration-smoke",
                **apply_migration_and_verify(
                    migration_path=migration_path,
                    database_url=args.database_url,
                    psql_bin=args.psql_bin,
                ),
            }
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        message = str(exc).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=PostgreSQL migration smoke failed::{message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
