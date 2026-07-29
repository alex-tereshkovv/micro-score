(() => {
  const demo = {
    users: {},
    organizations: {},
    modelVersions: {},
    sessions: {},
    staffInvites: {},
    staffInviteSecrets: {},
    staffInviteDeliveryAttempts: [],
    staffInviteDeliveryEvents: [],
    applications: [],
    decisions: {},
    simulations: [],
    timelines: {},
    auditEvents: [],
    nextTimelineId: 1,
    nextAuditId: 1,
    nextDecisionId: 1,
    nextApplicationNumber: 1,
  };
  const decisionWorkflowStatuses = {
    approve: "approved",
    review: "under_review",
    decline: "declined",
  };
  const terminalApplicationStatuses = new Set(["approved", "declined"]);
  const DEMO_SESSION_TTL_SECONDS = 8 * 60 * 60;
  const DEMO_MFA_CODE = "246810";
  const DEMO_INVITE_URL_BASE = "https://alex-tereshkovv.github.io/micro-score";
  const TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT = [
    "MICROSCORE_TRANSACTIONAL_EMAIL_API_KEY",
    "MICROSCORE_TRANSACTIONAL_EMAIL_FROM",
    "MICROSCORE_TRANSACTIONAL_EMAIL_TEMPLATE_ID",
    "MICROSCORE_TRANSACTIONAL_EMAIL_WEBHOOK_SECRET",
  ];
  const TRANSACTIONAL_EMAIL_OPTIONAL_ENVIRONMENT = [
    "MICROSCORE_TRANSACTIONAL_EMAIL_API_BASE_URL",
    "MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION",
    "MICROSCORE_TRANSACTIONAL_EMAIL_SEND_ENABLED",
  ];
  const INVITE_DELIVERY_WORKER_LIMITATION = "Invite Delivery Worker v1 is an audited local outbox runner. It can classify queued attempts, schedule retries, and dead-letter exhausted items, but it does not send messages through an external provider in this prototype.";
  const INVITE_DELIVERY_ADAPTER_LIMITATION = "Transactional Delivery Adapter Boundary v1 defines safe configuration, idempotency, payload, and webhook-correlation contracts, but external sending is disabled in this prototype. Queued worker attempts persist only token ids, not raw invite secrets, so a future production sender must use a dedicated one-time link issuance service or send while the raw token is still in process.";
  const INVITE_DELIVERY_ADAPTER_SAFE_PAYLOAD_FIELDS = [
    "provider",
    "attempt_id",
    "adapter_idempotency_key",
    "recipient",
    "channel",
    "template_id_env_name",
    "sender_env_name",
    "invite_token_preview",
    "organization_id",
  ];
  const INVITE_DELIVERY_ADAPTER_FORBIDDEN_PAYLOAD_FIELDS = [
    "raw_invite_token",
    "full_invite_url",
    "api_key",
    "webhook_secret",
    "authorization",
    "password",
  ];
  const INVITE_DELIVERY_ADAPTER_WEBHOOK_CORRELATION_FIELDS = [
    "provider",
    "provider_event_id",
    "attempt_id",
    "adapter_idempotency_key",
  ];
  const PRE_PILOT_RELEASE_TARGET = "public portfolio demo and controlled MFI validation planning, not real borrower onboarding";
  const PRE_PILOT_READINESS_LIMITATION = "Pre-Pilot Readiness Gate v1 aggregates live prototype evidence for release planning. It does not grant permission to collect real borrower data; production IdP/TOTP/WebAuthn, managed PostgreSQL, real KZT calibration, legal/privacy sign-off, and transactional invite delivery must be completed before a real pilot.";
  const POSTGRESQL_READINESS_LIMITATION = "PostgreSQL Migration Readiness v1 is a schema and parity contract. It does not connect to PostgreSQL, does not run production migrations, and does not make the prototype storage production-ready.";
  const POSTGRESQL_SCHEMA_INVENTORY = [
    {
      table: "mfi_organizations",
      present_in_sqlite: true,
      column_count: 4,
      primary_key_columns: ["id"],
      json_columns: [],
      tenant_scope_columns: [],
      migration_notes: [],
    },
    {
      table: "users",
      present_in_sqlite: true,
      column_count: 10,
      primary_key_columns: ["email"],
      json_columns: [],
      tenant_scope_columns: ["organization_id"],
      migration_notes: ["Preserve tenant scope in indexes, query filters, and optional row-level security."],
    },
    {
      table: "sessions",
      present_in_sqlite: true,
      column_count: 3,
      primary_key_columns: ["token"],
      json_columns: [],
      tenant_scope_columns: [],
      migration_notes: [],
    },
    {
      table: "staff_invites",
      present_in_sqlite: true,
      column_count: 18,
      primary_key_columns: ["token"],
      json_columns: [],
      tenant_scope_columns: ["organization_id"],
      migration_notes: ["Preserve tenant scope in indexes, query filters, and optional row-level security."],
    },
    {
      table: "staff_invite_delivery_attempts",
      present_in_sqlite: true,
      column_count: 16,
      primary_key_columns: ["attempt_id"],
      json_columns: [],
      tenant_scope_columns: [],
      migration_notes: [],
    },
    {
      table: "staff_invite_delivery_events",
      present_in_sqlite: true,
      column_count: 11,
      primary_key_columns: ["event_id"],
      json_columns: ["metadata_json"],
      tenant_scope_columns: [],
      migration_notes: ["Map JSON text columns to jsonb or a versioned JSON text strategy."],
    },
    {
      table: "loan_applications",
      present_in_sqlite: true,
      column_count: 10,
      primary_key_columns: ["id"],
      json_columns: ["behavioral_signals_json", "score_result_json"],
      tenant_scope_columns: ["organization_id"],
      migration_notes: [
        "Map JSON text columns to jsonb or a versioned JSON text strategy.",
        "Preserve tenant scope in indexes, query filters, and optional row-level security.",
      ],
    },
    {
      table: "application_decisions",
      present_in_sqlite: true,
      column_count: 7,
      primary_key_columns: ["id"],
      json_columns: [],
      tenant_scope_columns: [],
      migration_notes: [],
    },
    {
      table: "audit_events",
      present_in_sqlite: true,
      column_count: 6,
      primary_key_columns: ["id"],
      json_columns: ["details_json"],
      tenant_scope_columns: [],
      migration_notes: ["Map JSON text columns to jsonb or a versioned JSON text strategy."],
    },
    {
      table: "model_versions",
      present_in_sqlite: true,
      column_count: 13,
      primary_key_columns: ["version"],
      json_columns: ["metrics_json", "limitations_json"],
      tenant_scope_columns: [],
      migration_notes: ["Map JSON text columns to jsonb or a versioned JSON text strategy."],
    },
    {
      table: "portfolio_simulations",
      present_in_sqlite: true,
      column_count: 7,
      primary_key_columns: ["id"],
      json_columns: ["request_json", "result_json"],
      tenant_scope_columns: ["organization_id"],
      migration_notes: [
        "Map JSON text columns to jsonb or a versioned JSON text strategy.",
        "Preserve tenant scope in indexes, query filters, and optional row-level security.",
      ],
    },
  ];
  const POSTGRESQL_MIGRATION_ARTIFACTS = [
    {
      version: "0001_initial_schema",
      path: "migrations/postgresql/0001_initial_schema.sql",
      present: true,
      table_count: POSTGRESQL_SCHEMA_INVENTORY.length,
      jsonb_column_count: 8,
      tenant_scope_index_count: 4,
      tables: POSTGRESQL_SCHEMA_INVENTORY.map((table) => table.table),
      jsonb_columns: [
        "loan_applications.behavioral_signals_json",
        "loan_applications.score_result_json",
        "audit_events.details_json",
        "model_versions.metrics_json",
        "model_versions.limitations_json",
        "portfolio_simulations.request_json",
        "portfolio_simulations.result_json",
        "staff_invite_delivery_events.metadata_json",
      ],
      tenant_scope_indexes: [
        "idx_users_organization",
        "idx_applications_organization",
        "idx_staff_invites_organization",
        "idx_portfolio_simulations_organization",
      ],
      notes: [
        "Draft artifact covers required tables, JSONB mappings, and tenant indexes.",
      ],
    },
  ];
  const POSTGRESQL_REPOSITORY_ADAPTER_IMPLEMENTED_METHODS = [
    "create_model_version",
    "get_model_version",
    "get_active_model_version",
    "list_model_versions",
    "activate_model_version",
  ];
  const POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT = {
    module: "microscore_api.postgres_repository",
    version: "postgresql-repository-adapter-v3",
    status: "partial_method_group",
    stage: "model_registry_method_group_v1",
    present: true,
    runtime_enabled: false,
    method_count: 52,
    implemented_method_count: POSTGRESQL_REPOSITORY_ADAPTER_IMPLEMENTED_METHODS.length,
    implemented_methods: POSTGRESQL_REPOSITORY_ADAPTER_IMPLEMENTED_METHODS,
    pending_method_count: 47,
    completed_method_group_count: 1,
    completed_method_groups: ["model_registry"],
    read_only_method_count: 3,
    read_only_methods: ["get_model_version", "get_active_model_version", "list_model_versions"],
    write_method_count: 2,
    write_methods: ["create_model_version", "activate_model_version"],
    method_groups: [
      {
        key: "identity_access",
        label: "Identity, MFA, and session lifecycle",
        method_count: 11,
        methods: ["create_user", "get_user", "list_users", "disable_user", "reactivate_user", "attest_user_mfa", "create_session", "get_user_by_token", "list_active_sessions", "revoke_session", "revoke_session_by_id"],
      },
      {
        key: "organizations",
        label: "MFI organization and tenant assignment",
        method_count: 4,
        methods: ["create_organization", "get_organization", "list_organizations", "assign_user_organization"],
      },
      {
        key: "staff_invites_delivery",
        label: "Staff invites, delivery outbox, worker, and webhooks",
        method_count: 15,
        methods: ["create_staff_invite", "get_staff_invite", "list_staff_invites", "mark_staff_invite_accepted", "mark_staff_invite_revoked", "mark_staff_invite_delivered", "record_staff_invite_delivery_attempt", "record_staff_invite_delivery_event", "get_staff_invite_delivery_attempt", "get_staff_invite_delivery_event", "list_staff_invite_delivery_attempts", "list_staff_invite_delivery_events", "list_staff_invite_delivery_outbox_attempts", "update_staff_invite_delivery_attempt_status", "update_staff_invite_delivery_worker_state"],
      },
      {
        key: "application_lifecycle",
        label: "Borrower application lifecycle, scoring, review, and decisions",
        method_count: 10,
        methods: ["create_application", "get_application", "list_applications", "list_borrower_applications", "assign_application_organization", "update_application_score", "record_application_decision", "list_application_decisions", "list_application_timeline", "clear_applications"],
      },
      {
        key: "model_registry",
        label: "Model registry and active-version governance",
        method_count: 5,
        methods: ["create_model_version", "get_model_version", "get_active_model_version", "list_model_versions", "activate_model_version"],
      },
      {
        key: "portfolio_analytics",
        label: "Portfolio simulations and MFI analytics",
        method_count: 5,
        methods: ["create_portfolio_simulation", "get_portfolio_simulation", "list_portfolio_simulations", "segment_analytics", "decision_analytics"],
      },
      {
        key: "audit",
        label: "Audit event recording and review",
        method_count: 2,
        methods: ["record_audit_event", "list_audit_events"],
      },
    ].map((group) => {
      const implementedMethods = group.methods.filter((method) => POSTGRESQL_REPOSITORY_ADAPTER_IMPLEMENTED_METHODS.includes(method));
      const pendingMethods = group.methods.filter((method) => !POSTGRESQL_REPOSITORY_ADAPTER_IMPLEMENTED_METHODS.includes(method));
      return {
        ...group,
        implemented_method_count: implementedMethods.length,
        implemented_methods: implementedMethods,
        pending_method_count: pendingMethods.length,
        pending_methods: pendingMethods,
      };
    }),
    limitation: "PostgreSQL Repository Adapter v3 implements the model registry method group through an injected DB-API compatible connection factory. Runtime backend selection remains disabled until identity, tenant-scoped application, invite, simulation, analytics, and audit flows have repository parity coverage.",
  };
  const borrowerStatusMessages = {
    submitted: "Application received. It is waiting for the MFI to begin review.",
    scored: "The MFI completed its internal assessment. A human review is still required.",
    under_review: "The MFI marked this application for manual review. A final outcome has not been recorded yet.",
    approved: "The MFI recorded an approval decision. This is a final status in the demo portal.",
    declined: "The MFI recorded a decline decision. This is a final status in the demo portal.",
  };

  const demoUsers = [
    ["borrower@test.com", "borrower", null],
    ["analyst@test.com", "mfi_analyst", "pavlodar-demo-mfi"],
    ["admin@test.com", "admin", null],
  ];

  const commonPasswords = new Set([
    "1234567890",
    "admin123",
    "letmein123",
    "password",
    "password123",
    "qwerty123",
  ]);

  function passwordPolicyViolations(password) {
    const value = String(password || "");
    const violations = [];
    if (value.length < 10) violations.push("use at least 10 characters");
    if (!/[a-z]/.test(value)) violations.push("include a lowercase letter");
    if (!/[A-Z]/.test(value)) violations.push("include an uppercase letter");
    if (!/[0-9]/.test(value)) violations.push("include a number");
    if (/^[a-z0-9]+$/i.test(value)) violations.push("include a symbol");
    if (commonPasswords.has(value.trim().toLowerCase())) violations.push("avoid a common password");
    return violations;
  }

  const forbiddenSignalTokens = new Set([
    "address",
    "biometric",
    "email",
    "iin",
    "latitude",
    "longitude",
    "passport",
    "phone",
    "photo",
    "voice",
  ]);
  const forbiddenSignalPhrases = [
    "bank_statement",
    "device_fingerprint",
    "first_name",
    "full_name",
    "id_number",
    "last_name",
    "national_id",
    "phone_book",
    "precise_geolocation",
    "raw_transaction",
    "social_media",
    "transaction_description",
    "voice_recording",
  ];

  function normalizedSignalKey(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function signalKeyIsForbidden(key) {
    const normalized = normalizedSignalKey(key);
    const tokens = normalized.split("_");
    return (
      tokens.some((token) => forbiddenSignalTokens.has(token)) ||
      forbiddenSignalPhrases.some((phrase) => normalized.includes(phrase))
    );
  }

  function findForbiddenSignalPaths(value, path = "behavioral_signals") {
    const matches = [];
    if (Array.isArray(value)) {
      value.forEach((child, index) => {
        matches.push(...findForbiddenSignalPaths(child, `${path}[${index}]`));
      });
    } else if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, child]) => {
        const childPath = `${path}.${key}`;
        if (signalKeyIsForbidden(key)) matches.push(childPath);
        matches.push(...findForbiddenSignalPaths(child, childPath));
      });
    }
    return [...new Set(matches)].sort();
  }

  function validateApplicationPrivacy(payload) {
    if (payload.consent_confirmed !== true) {
      throw new Error("Confirm synthetic-data consent before submitting an application");
    }
    if (!String(payload.consent_version || "").trim()) {
      throw new Error("A consent version is required for auditability");
    }
    const forbiddenPaths = findForbiddenSignalPaths(payload.behavioral_signals || {});
    if (forbiddenPaths.length) {
      throw new Error(`Remove sensitive personal fields: ${forbiddenPaths.join(", ")}`);
    }
  }

  function validateApplicationContract(payload) {
    const intake = window.MicroScoreApplicationIntake || globalThis.MicroScoreApplicationIntake;
    if (!intake) throw new Error("Application intake validation is unavailable");
    const result = intake.validateApplicationIntake(payload);
    if (!result.valid) {
      throw new Error(`Application validation failed: ${intake.formatApplicationIntakeErrors(result.errors)}`);
    }
  }

  const seedApplications = [
    {
      borrower_email: "borrower@test.com",
      requested_amount: 3000,
      purpose: "working capital",
      district: "Pavlodar city",
      settlement_type: "urban",
      annual_income: 52000,
      total_outstanding_debt: 6500,
      mobile_banking_logins: 18,
      online_transfer_frequency: 7,
      atm_withdrawal_frequency: 2,
      avg_deposit_amount: 1400,
      debit_card_spending: 900,
      num_open_loans: 1,
      late_payment_count: 0,
      gender: "Female",
      employment_status: "Self-employed",
      decision: "approve",
      decision_note: "Starter loan approved with standard follow-up.",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 4200,
      purpose: "farm equipment repair",
      district: "Bayanaul",
      settlement_type: "rural",
      annual_income: 38000,
      total_outstanding_debt: 9700,
      mobile_banking_logins: 8,
      online_transfer_frequency: 3,
      atm_withdrawal_frequency: 5,
      avg_deposit_amount: 900,
      debit_card_spending: 680,
      num_open_loans: 2,
      late_payment_count: 1,
      gender: "Male",
      employment_status: "Self-employed",
      decision: "review",
      decision_note: "Request income context before final decision.",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 2500,
      purpose: "household inventory",
      district: "Ekibastuz",
      settlement_type: "industrial_city",
      annual_income: 47000,
      total_outstanding_debt: 5400,
      mobile_banking_logins: 22,
      online_transfer_frequency: 11,
      atm_withdrawal_frequency: 1,
      avg_deposit_amount: 1600,
      debit_card_spending: 1100,
      num_open_loans: 1,
      late_payment_count: 0,
      gender: "Female",
      employment_status: "Employed",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 6100,
      purpose: "seasonal inventory",
      district: "Akkuly",
      settlement_type: "rural",
      annual_income: 31000,
      total_outstanding_debt: 14200,
      mobile_banking_logins: 4,
      online_transfer_frequency: 1,
      atm_withdrawal_frequency: 7,
      avg_deposit_amount: 450,
      debit_card_spending: 420,
      num_open_loans: 3,
      late_payment_count: 2,
      gender: "Male",
      employment_status: "Self-employed",
      decision: "decline",
      decision_note: "Debt load and recent payment history require a smaller offer.",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 1800,
      purpose: "education fees",
      district: "Aksu",
      settlement_type: "industrial_city",
      annual_income: 44000,
      total_outstanding_debt: 3100,
      mobile_banking_logins: 15,
      online_transfer_frequency: 6,
      atm_withdrawal_frequency: 2,
      avg_deposit_amount: 1200,
      debit_card_spending: 760,
      num_open_loans: 0,
      late_payment_count: 0,
      gender: "Female",
      employment_status: "Employed",
      decision: "approve",
      decision_note: "Low debt burden and active digital behavior.",
    },
  ];

  function nowIso() {
    return new Date().toISOString();
  }

  function sessionMetadata(createdAt = new Date()) {
    const created = createdAt instanceof Date ? createdAt : new Date(createdAt);
    const expiresAt = new Date(created.getTime() + DEMO_SESSION_TTL_SECONDS * 1000);
    return {
      session_created_at: created.toISOString(),
      session_expires_at: expiresAt.toISOString(),
      session_ttl_seconds: DEMO_SESSION_TTL_SECONDS,
    };
  }

  function createDemoSession(email) {
    const token = `mock-token-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const metadata = sessionMetadata();
    demo.sessions[token] = { email, ...metadata };
    return { token, ...metadata };
  }

  function sessionIdForToken(rawToken) {
    let hash = 0x811c9dc5;
    String(rawToken).split("").forEach((character) => {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 0x01000193);
    });
    return `static-session-${(hash >>> 0).toString(16).padStart(8, "0")}-${String(rawToken).length}`;
  }

  function publicStaffSession(token, record, currentToken = null) {
    const user = demo.users[record.email];
    if (!user || !["admin", "mfi_analyst"].includes(user.role) || user.disabled_at) return null;
    if (record.session_expires_at && Date.parse(record.session_expires_at) <= Date.now()) {
      delete demo.sessions[token];
      return null;
    }
    const sessionId = sessionIdForToken(token);
    return {
      session_id: sessionId,
      session_preview: `${sessionId.slice(0, 12)}...`,
      email: user.email,
      role: user.role,
      organization_id: user.organization_id || null,
      session_created_at: record.session_created_at,
      session_expires_at: record.session_expires_at,
      session_ttl_seconds: record.session_ttl_seconds || DEMO_SESSION_TTL_SECONDS,
      is_current_session: token === currentToken,
    };
  }

  function activeStaffSessions(currentToken = null) {
    return Object.entries(demo.sessions)
      .map(([token, record]) => publicStaffSession(token, record, currentToken))
      .filter(Boolean)
      .sort((left, right) => right.session_created_at.localeCompare(left.session_created_at));
  }

  function staffInviteTokenId(rawToken) {
    let hash = 0x811c9dc5;
    String(rawToken).split("").forEach((character) => {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 0x01000193);
    });
    return `static-${(hash >>> 0).toString(16).padStart(8, "0")}-${String(rawToken).length}`;
  }

  function staffInviteTokenPreview(tokenId) {
    return `${String(tokenId).slice(0, 12)}...`;
  }

  function staffInviteDeliveryAdapterIdempotencyKey(attempt) {
    return staffInviteTokenId(`${attempt.provider}:${attempt.attempt_id}:${attempt.invite_token}`);
  }

  function publicStaffInvite(invite, rawToken = null) {
    const attempts = staffInviteDeliveryAttempts(invite.token_id);
    const lastAttempt = attempts[0] || null;
    const events = staffInviteDeliveryEvents(invite.token_id);
    const lastEvent = events[0] || null;
    const response = {
      token_id: invite.token_id,
      token_preview: invite.token_preview,
      email: invite.email,
      role: invite.role,
      organization_id: invite.organization_id,
      created_by: invite.created_by,
      created_at: invite.created_at,
      expires_at: invite.expires_at,
      accepted_at: invite.accepted_at,
      accepted_by: invite.accepted_by,
      revoked_at: invite.revoked_at,
      revoked_by: invite.revoked_by,
      delivered_at: invite.delivered_at,
      delivered_by: invite.delivered_by,
      delivery_channel: invite.delivery_channel,
      delivery_recipient: invite.delivery_recipient,
      delivery_url_base: invite.delivery_url_base,
      delivery_note: invite.delivery_note,
      delivery_attempt_count: attempts.length,
      last_delivery_attempt_at: lastAttempt?.attempted_at || null,
      last_delivery_status: lastAttempt?.status || null,
      last_delivery_provider: lastAttempt?.provider || null,
      delivery_event_count: events.length,
      last_delivery_event_at: lastEvent?.received_at || null,
      last_delivery_event_type: lastEvent?.event_type || null,
    };
    if (rawToken) {
      response.token = rawToken;
      response.invite_url = `${DEMO_INVITE_URL_BASE}/#/accept-staff-invite?token=${encodeURIComponent(rawToken)}`;
    }
    if (Object.prototype.hasOwnProperty.call(invite, "was_already_delivered")) {
      response.was_already_delivered = invite.was_already_delivered;
    }
    return response;
  }

  function publicStaffInviteDeliveryAttempt(attempt) {
    return {
      attempt_id: attempt.attempt_id,
      invite_token_id: attempt.invite_token,
      attempted_at: attempt.attempted_at,
      attempted_by: attempt.attempted_by,
      provider: attempt.provider,
      status: attempt.status,
      channel: attempt.channel,
      recipient: attempt.recipient,
      delivery_url_base: attempt.delivery_url_base,
      note: attempt.note,
      error: attempt.error,
      worker_status: attempt.worker_status || "completed",
      worker_attempt_count: Number(attempt.worker_attempt_count || 0),
      next_worker_run_at: attempt.next_worker_run_at || null,
      dead_letter_at: attempt.dead_letter_at || null,
      last_worker_error: attempt.last_worker_error || null,
    };
  }

  function publicStaffInviteDeliveryWebhookEvent(event, deliveryRecorded = false) {
    return {
      event_id: event.event_id,
      provider_event_id: event.provider_event_id,
      attempt_id: event.attempt_id,
      invite_token_id: event.invite_token,
      provider: event.provider,
      event_type: event.event_type,
      mapped_attempt_status: event.mapped_attempt_status,
      received_at: event.received_at,
      occurred_at: event.occurred_at,
      recipient: event.recipient,
      error: event.error,
      was_duplicate: Boolean(event.was_duplicate),
      delivery_recorded: Boolean(deliveryRecorded),
    };
  }

  function staffInviteDeliveryAttempts(tokenId) {
    return demo.staffInviteDeliveryAttempts
      .filter((attempt) => attempt.invite_token === tokenId)
      .sort((left, right) => (
        right.attempted_at.localeCompare(left.attempted_at)
        || Number(right.attempt_sequence || 0) - Number(left.attempt_sequence || 0)
        || right.attempt_id.localeCompare(left.attempt_id)
      ));
  }

  function staffInviteDeliveryEvents(tokenId) {
    return demo.staffInviteDeliveryEvents
      .filter((event) => event.invite_token === tokenId)
      .sort((left, right) => (
        right.received_at.localeCompare(left.received_at)
        || right.event_id.localeCompare(left.event_id)
      ));
  }

  function mapInviteDeliveryWebhookStatus(eventType) {
    return {
      delivered: "sent",
      bounced: "failed",
      failed: "failed",
      deferred: "queued",
    }[eventType] || "queued";
  }

  function recordStaffInviteDeliveryWebhookEvent(payload) {
    const provider = String(payload.provider || "").trim();
    const providerEventId = String(payload.provider_event_id || "").trim();
    const attemptId = String(payload.attempt_id || "").trim();
    const eventType = String(payload.event_type || "").trim();
    if (!provider || !providerEventId || !attemptId) throw new Error("Webhook event id, provider, and attempt id are required");
    if (!["delivered", "bounced", "failed", "deferred"].includes(eventType)) throw new Error("Unsupported webhook event type");
    const attempt = demo.staffInviteDeliveryAttempts.find((row) => row.attempt_id === attemptId);
    if (!attempt) throw new Error("Staff invite delivery attempt not found");
    if (attempt.provider !== provider) throw new Error("Webhook provider does not match delivery attempt provider");
    const invite = demo.staffInvites[attempt.invite_token];
    if (!invite) throw new Error("Staff invite not found");
    const duplicate = demo.staffInviteDeliveryEvents.find((row) => (
      row.provider === provider && row.provider_event_id === providerEventId
    ));
    if (duplicate) {
      duplicate.was_duplicate = true;
      return { event: duplicate, deliveryRecorded: false };
    }

    const mappedStatus = mapInviteDeliveryWebhookStatus(eventType);
    const event = {
      event_id: `invite-delivery-event-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      provider,
      provider_event_id: providerEventId,
      attempt_id: attemptId,
      invite_token: attempt.invite_token,
      event_type: eventType,
      mapped_attempt_status: mappedStatus,
      received_at: nowIso(),
      occurred_at: payload.occurred_at || null,
      recipient: payload.recipient || null,
      error: payload.error || null,
      metadata: payload.metadata || {},
      was_duplicate: false,
    };
    demo.staffInviteDeliveryEvents.push(event);
    attempt.status = mappedStatus;
    attempt.error = payload.error || null;
    attempt.worker_status = mappedStatus === "queued" ? "retry_scheduled" : "completed";
    attempt.next_worker_run_at = mappedStatus === "queued" ? new Date(Date.now() + 5 * 60 * 1000).toISOString() : null;
    attempt.dead_letter_at = null;
    attempt.last_worker_error = mappedStatus === "queued" ? (payload.error || null) : null;

    let deliveryRecorded = false;
    if (mappedStatus === "sent" && !invite.delivered_at) {
      invite.delivered_at = nowIso();
      invite.delivered_by = null;
      invite.delivery_channel = attempt.channel;
      invite.delivery_recipient = payload.recipient || attempt.recipient;
      invite.delivery_url_base = attempt.delivery_url_base;
      invite.delivery_note = attempt.note;
      deliveryRecorded = true;
      addAudit("staff_invite_delivered", "staff_invite", invite.token_id, null, {
        email: invite.email,
        role: invite.role,
        organization_id: invite.organization_id,
        token_preview: invite.token_preview,
        delivery_attempt_id: attemptId,
        delivery_provider: provider,
        delivery_channel: attempt.channel,
        delivery_recipient: payload.recipient || attempt.recipient,
        delivery_url_base: attempt.delivery_url_base,
        source: "delivery_webhook",
        provider_event_id: providerEventId,
      });
    }
    addAudit("staff_invite_delivery_webhook_received", "staff_invite_delivery_event", event.event_id, null, {
      staff_invite_token_id: invite.token_id,
      staff_invite_token_preview: invite.token_preview,
      delivery_attempt_id: attemptId,
      provider,
      provider_event_id: providerEventId,
      event_type: eventType,
      mapped_attempt_status: mappedStatus,
      recipient: payload.recipient || null,
      error_present: Boolean(payload.error),
      metadata_keys: Object.keys(payload.metadata || {}).sort(),
      delivery_recorded: deliveryRecorded,
    });
    return { event, deliveryRecorded };
  }

  function staffInviteDeliveryProviderResult(provider) {
    const profile = staffInviteDeliveryProviderProfile(provider);
    return {
      provider: profile.provider,
      status: profile.attempt_status,
      error: profile.error,
    };
  }

  function providerConfigurationDefaults() {
    return {
      configuration_status: "not_required",
      configuration_ready: true,
      required_environment: [],
      configured_environment: [],
      missing_environment: [],
      configuration_warnings: [],
    };
  }

  function transactionalEmailConfigurationProfile() {
    return {
      configuration_status: "missing",
      configuration_ready: false,
      required_environment: TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT.slice(),
      optional_environment: TRANSACTIONAL_EMAIL_OPTIONAL_ENVIRONMENT.slice(),
      configured_environment: [],
      missing_environment: TRANSACTIONAL_EMAIL_REQUIRED_ENVIRONMENT.slice(),
      configuration_warnings: [],
    };
  }

  function staffInviteDeliveryProviderProfile(provider) {
    const providerName = String(provider || "local_outbox").trim() || "local_outbox";
    const profiles = {
      local_outbox: {
        attempt_status: "sent",
        mode: "local_audit_outbox",
        production_ready: false,
        sends_message: false,
        audit_only: true,
        requires_external_secret: false,
        summary: "Records a local audited outbox receipt and marks delivery sent inside the static demo.",
        action: "Replace with a transactional email or secure-message provider before pilot onboarding.",
        error: null,
      },
      manual_receipt: {
        attempt_status: "sent",
        mode: "manual_receipt",
        production_ready: false,
        sends_message: false,
        audit_only: true,
        requires_external_secret: false,
        summary: "Records that an operator manually copied or sent the invite link.",
        action: "Use only for demos; require transactional delivery before real staff onboarding.",
        error: null,
      },
      local_queue: {
        attempt_status: "queued",
        mode: "local_queue",
        production_ready: false,
        sends_message: false,
        audit_only: true,
        requires_external_secret: false,
        summary: "Queues a local delivery attempt without marking the invite delivered.",
        action: "Retry through a working provider, rotate stale links, or revoke the invite.",
        error: null,
      },
      local_fail: {
        attempt_status: "failed",
        mode: "local_failure_simulator",
        production_ready: false,
        sends_message: false,
        audit_only: true,
        requires_external_secret: false,
        summary: "Simulates a failed local delivery provider for release-gate coverage.",
        action: "Retry with a working provider and keep the failure visible in audit events.",
        error: "Local delivery provider simulated failure.",
      },
      transactional_email: {
        attempt_status: "queued",
        mode: "transactional_email_contract",
        production_ready: false,
        sends_message: false,
        audit_only: false,
        requires_external_secret: true,
        summary: "Validates the future transactional email adapter configuration and records safe audited delivery attempts.",
        action: "Set API key, sender, template, webhook secret, secret rotation, bounce handling, and delivery webhooks before production sends.",
        error: "Transactional email provider is missing required configuration.",
      },
    };
    const configuration = providerName === "transactional_email"
      ? transactionalEmailConfigurationProfile()
      : providerConfigurationDefaults();
    const profile = profiles[providerName] || {
      attempt_status: "queued",
      mode: "unknown_contract",
      production_ready: false,
      configuration_status: "missing",
      configuration_ready: false,
      sends_message: false,
      audit_only: true,
      requires_external_secret: true,
      required_environment: [],
      configured_environment: [],
      missing_environment: [],
      configuration_warnings: [`Provider '${providerName}' is not registered in the invite delivery contract.`],
      summary: "Delivery provider has no local sender implementation yet.",
      action: "Register provider contract, secret handling, webhook/audit mapping, and failure semantics before use.",
      error: "Delivery provider has no local sender implementation yet.",
    };
    return {
      provider: providerName,
      configured: providerName === "local_outbox",
      requires_https_invite_url: true,
      ...configuration,
      ...profile,
    };
  }

  function recordStaffInviteDeliveryAttempt(
    invite,
    actorEmail,
    {
      provider = "local_outbox",
      channel = "email",
      recipient = null,
      note = null,
    } = {},
  ) {
    const normalizedRecipient = String(recipient || invite.email).trim() || invite.email;
    const normalizedNote = note ? String(note).trim() : null;
    const providerResult = staffInviteDeliveryProviderResult(provider);
    const attemptedAt = nowIso();
    const attempt = {
      attempt_id: `invite-delivery-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      attempt_sequence: demo.staffInviteDeliveryAttempts.length + 1,
      invite_token: invite.token_id,
      attempted_at: attemptedAt,
      attempted_by: actorEmail,
      provider: providerResult.provider,
      status: providerResult.status,
      channel,
      recipient: normalizedRecipient,
      delivery_url_base: DEMO_INVITE_URL_BASE,
      note: normalizedNote,
      error: providerResult.error,
      worker_status: providerResult.status === "queued" ? "queued" : "completed",
      worker_attempt_count: 0,
      next_worker_run_at: providerResult.status === "queued" ? attemptedAt : null,
      dead_letter_at: null,
      last_worker_error: null,
    };
    demo.staffInviteDeliveryAttempts.push(attempt);
    addAudit("staff_invite_delivery_attempted", "staff_invite_delivery_attempt", attempt.attempt_id, actorEmail, {
      staff_invite_token_id: invite.token_id,
      staff_invite_token_preview: invite.token_preview,
      provider: attempt.provider,
      status: attempt.status,
      delivery_channel: attempt.channel,
      delivery_recipient: attempt.recipient,
      delivery_url_base: attempt.delivery_url_base,
      note_present: Boolean(attempt.note),
      error_present: Boolean(attempt.error),
    });
    const wasAlreadyDelivered = Boolean(invite.delivered_at);
    if (attempt.status === "sent" && !wasAlreadyDelivered) {
      invite.delivered_at = nowIso();
      invite.delivered_by = actorEmail;
      invite.delivery_channel = attempt.channel;
      invite.delivery_recipient = attempt.recipient;
      invite.delivery_url_base = attempt.delivery_url_base;
      invite.delivery_note = attempt.note;
      addAudit("staff_invite_delivered", "staff_invite", invite.token_id, actorEmail, {
        email: invite.email,
        role: invite.role,
        organization_id: invite.organization_id,
        token_preview: invite.token_preview,
        delivery_attempt_id: attempt.attempt_id,
        delivery_provider: attempt.provider,
        delivery_channel: invite.delivery_channel,
        delivery_recipient: invite.delivery_recipient,
        delivery_url_base: invite.delivery_url_base,
        note_present: Boolean(invite.delivery_note),
      });
    }
    return { attempt, wasAlreadyDelivered };
  }

  function createStaffInviteRecord(payload, actorEmail) {
    const email = String(payload.email || "").trim().toLowerCase();
    if (!email) throw new Error("Invite email is required");
    const createdAt = new Date();
    const expiresInHours = clamp(number(payload.expires_in_hours, 48), 1, 168);
    const expiresAt = new Date(createdAt.getTime() + expiresInHours * 60 * 60 * 1000);
    const token = `staff-invite-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const tokenId = staffInviteTokenId(token);
    const invite = {
      token_id: tokenId,
      token_preview: staffInviteTokenPreview(tokenId),
      email,
      role: payload.role || "mfi_analyst",
      organization_id: payload.organization_id,
      created_by: actorEmail,
      created_at: createdAt.toISOString(),
      expires_at: expiresAt.toISOString(),
      accepted_at: null,
      accepted_by: null,
      revoked_at: null,
      revoked_by: null,
      delivered_at: null,
      delivered_by: null,
      delivery_channel: null,
      delivery_recipient: null,
      delivery_url_base: null,
      delivery_note: null,
    };
    demo.staffInvites[tokenId] = invite;
    demo.staffInviteSecrets[token] = tokenId;
    return publicStaffInvite(invite, token);
  }

  function staffInviteLifecycleStatus(invite) {
    if (invite.revoked_at) return "revoked";
    if (invite.accepted_at) return "accepted";
    if (Date.parse(invite.expires_at) <= Date.now()) return "expired";
    return "pending";
  }

  function activePendingInviteForEmail(email, excludeTokenId = null) {
    const normalizedEmail = String(email || "").trim().toLowerCase();
    return Object.values(demo.staffInvites).find((invite) => (
      invite.token_id !== excludeTokenId
      && invite.email === normalizedEmail
      && !invite.accepted_at
      && !invite.revoked_at
      && Date.parse(invite.expires_at) > Date.now()
    ));
  }

  function staffInviteHealth(invites, windowHours = 24) {
    const now = new Date();
    const expiringDeadline = new Date(now.getTime() + windowHours * 60 * 60 * 1000);
    const health = {
      status: "ok",
      total_count: invites.length,
      active_pending_count: 0,
      expiring_soon_count: 0,
      expired_pending_count: 0,
      accepted_count: 0,
      revoked_count: 0,
      action_required_count: 0,
      window_hours: windowHours,
      oldest_pending_created_at: null,
      next_expiring_at: null,
      recommended_action: "No pending staff invite rotation action required.",
    };
    let oldestPending = null;
    let nextExpiring = null;
    invites.forEach((invite) => {
      if (invite.accepted_at) {
        health.accepted_count += 1;
        return;
      }
      if (invite.revoked_at) {
        health.revoked_count += 1;
        return;
      }
      const createdAt = new Date(invite.created_at);
      const expiresAt = new Date(invite.expires_at);
      if (!oldestPending || createdAt < oldestPending) oldestPending = createdAt;
      if (expiresAt <= now) {
        health.expired_pending_count += 1;
        return;
      }
      health.active_pending_count += 1;
      if (!nextExpiring || expiresAt < nextExpiring) nextExpiring = expiresAt;
      if (expiresAt <= expiringDeadline) health.expiring_soon_count += 1;
    });
    health.action_required_count = health.expired_pending_count + health.expiring_soon_count;
    health.oldest_pending_created_at = oldestPending ? oldestPending.toISOString() : null;
    health.next_expiring_at = nextExpiring ? nextExpiring.toISOString() : null;
    if (health.action_required_count) {
      health.status = "attention";
      health.recommended_action = "Review expired or soon-expiring staff invites; revoke stale links and create fresh invites only when onboarding is still needed.";
    }
    return health;
  }

  function inviteDeliveryReadiness() {
    const configuredProvider = "local_outbox";
    const providers = [
      "local_outbox",
      "manual_receipt",
      "local_queue",
      "local_fail",
      "transactional_email",
    ].map((provider) => ({
      ...staffInviteDeliveryProviderProfile(provider),
      configured: provider === configuredProvider,
    }));
    const configuredProfile = providers.find((row) => row.configured) || {};
    const activePendingInvites = Object.values(demo.staffInvites).filter((invite) => (
      !invite.accepted_at
      && !invite.revoked_at
      && Date.parse(invite.expires_at) > Date.now()
    ));
    const undeliveredInvites = activePendingInvites.filter((invite) => !invite.delivered_at);
    const failedDeliveryInvites = activePendingInvites.filter((invite) => {
      const attempts = staffInviteDeliveryAttempts(invite.token_id);
      return attempts[0]?.status === "failed";
    });
    let inviteUrlHttps = false;
    let inviteUrlLocal = false;
    try {
      const parsed = new URL(DEMO_INVITE_URL_BASE);
      inviteUrlHttps = parsed.protocol === "https:";
      inviteUrlLocal = ["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(parsed.hostname);
    } catch (_error) {
      inviteUrlHttps = false;
      inviteUrlLocal = false;
    }
    const blockers = [];
    const warnings = [];
    if (!configuredProfile.production_ready) {
      blockers.push({
        key: "delivery_provider_not_production_ready",
        severity: "blocker",
        summary: `Configured provider '${configuredProvider}' is ${configuredProfile.mode} and is not production-ready.`,
        action: configuredProfile.action,
      });
    }
    if (configuredProfile.missing_environment?.length) {
      blockers.push({
        key: "delivery_provider_configuration_missing",
        severity: "blocker",
        summary: `Configured provider '${configuredProvider}' is missing ${configuredProfile.missing_environment.length} required environment variable(s).`,
        action: "Set the required transactional email environment variables without exposing secret values in logs or API responses.",
      });
    }
    if (configuredProfile.configuration_warnings?.length) {
      blockers.push({
        key: "delivery_provider_configuration_invalid",
        severity: "blocker",
        summary: `Configured provider '${configuredProvider}' has invalid delivery configuration.`,
        action: "Fix provider sender/API URL configuration before enabling delivery attempts.",
      });
    }
    if (!inviteUrlHttps) {
      blockers.push({
        key: "invite_url_not_https",
        severity: "blocker",
        summary: `Invite URL base '${DEMO_INVITE_URL_BASE}' is not HTTPS.`,
        action: "Use a verified HTTPS invite origin before real staff onboarding.",
      });
    }
    if (inviteUrlLocal) {
      blockers.push({
        key: "invite_url_local_origin",
        severity: "blocker",
        summary: `Invite URL base '${DEMO_INVITE_URL_BASE}' points to a local host.`,
        action: "Move invite links to the deployed HTTPS application origin.",
      });
    }
    if (undeliveredInvites.length) {
      blockers.push({
        key: "undelivered_active_invites",
        severity: "blocker",
        summary: `${undeliveredInvites.length} active pending staff invite(s) do not have audited delivery metadata.`,
        action: "Record delivery, retry through a working provider, rotate, or revoke each invite.",
      });
    }
    if (failedDeliveryInvites.length) {
      warnings.push({
        key: "failed_latest_delivery_attempts",
        severity: "warning",
        summary: `${failedDeliveryInvites.length} active pending staff invite(s) have a failed latest delivery attempt.`,
        action: "Retry through a working provider or rotate/revoke the invite.",
      });
    }
    return {
      status: blockers.length ? "blocked" : warnings.length ? "review" : "ready",
      generated_at: nowIso(),
      configured_provider: configuredProvider,
      default_provider: "local_outbox",
      invite_url_base: DEMO_INVITE_URL_BASE,
      invite_url_https: inviteUrlHttps,
      invite_url_local: inviteUrlLocal,
      active_pending_invite_count: activePendingInvites.length,
      undelivered_active_invite_count: undeliveredInvites.length,
      failed_latest_attempt_count: failedDeliveryInvites.length,
      providers,
      production_blockers: blockers,
      warnings,
      next_required_controls: blockers.concat(warnings),
      limitation: "Staff Invite Delivery Readiness v2 validates provider contract, HTTPS origin, secret/configuration presence, and audited delivery evidence. It does not expose secret values and the static transactional email adapter records attempts without sending external email.",
    };
  }

  function inviteDeliveryAdapterReadiness() {
    const configuration = transactionalEmailConfigurationProfile();
    const blockers = [
      {
        key: "external_send_adapter_disabled",
        severity: "blocker",
        summary: "Transactional email external sends are disabled in the prototype adapter.",
        action: "Implement a signed provider adapter with timeout, retry, idempotency, secret isolation, and delivery webhook reconciliation before enabling sends.",
      },
      {
        key: "invite_secret_material_not_available",
        severity: "blocker",
        summary: "Queued worker attempts persist invite token ids and previews only, not raw invite tokens or full invite URLs.",
        action: "Add a production one-time link issuance service or send while the raw invite token is still in process; do not persist raw invite secrets.",
      },
      {
        key: "transactional_email_configuration_missing",
        severity: "blocker",
        summary: `Transactional email adapter is missing required environment variable(s): ${configuration.missing_environment.length}.`,
        action: "Set API key, sender, template id, and webhook secret using secret storage; never return secret values through API responses.",
      },
      {
        key: "secret_rotation_version_missing",
        severity: "blocker",
        summary: "Transactional email secret version is not declared for rotation evidence.",
        action: "Set MICROSCORE_TRANSACTIONAL_EMAIL_SECRET_VERSION to a non-secret rotation label before production adapter tests.",
      },
    ];
    return {
      status: "blocked",
      generated_at: nowIso(),
      provider: "transactional_email",
      adapter_mode: "prototype_boundary_no_external_send",
      send_adapter_ready: false,
      external_send_enabled: false,
      configuration_status: configuration.configuration_status,
      configuration_ready: configuration.configuration_ready,
      secret_rotation_ready: false,
      idempotency_key_strategy: "sha256(provider:attempt_id:invite_token_id)",
      safe_payload_fields: INVITE_DELIVERY_ADAPTER_SAFE_PAYLOAD_FIELDS.slice(),
      forbidden_payload_fields: INVITE_DELIVERY_ADAPTER_FORBIDDEN_PAYLOAD_FIELDS.slice(),
      webhook_correlation_fields: INVITE_DELIVERY_ADAPTER_WEBHOOK_CORRELATION_FIELDS.slice(),
      required_environment: configuration.required_environment,
      optional_environment: configuration.optional_environment,
      configured_environment: configuration.configured_environment,
      missing_environment: configuration.missing_environment,
      blockers,
      warnings: [],
      next_required_controls: blockers,
      limitation: INVITE_DELIVERY_ADAPTER_LIMITATION,
    };
  }

  function staffInviteDeliveryWorkerError(provider) {
    return `Invite delivery worker cannot send through provider '${provider}' in this prototype.`;
  }

  function staffInviteDeliveryOutboxItem(attempt, now = new Date()) {
    const invite = demo.staffInvites[attempt.invite_token] || {};
    const activePending = Boolean(
      invite.token_id
      && !invite.accepted_at
      && !invite.revoked_at
      && Date.parse(invite.expires_at) > now.getTime(),
    );
    const workerStatus = attempt.worker_status || "completed";
    const nextWorkerRunAt = attempt.next_worker_run_at || null;
    const dueAt = nextWorkerRunAt ? Date.parse(nextWorkerRunAt) : null;
    const lastEvent = demo.staffInviteDeliveryEvents
      .filter((event) => event.attempt_id === attempt.attempt_id)
      .sort((left, right) => (
        right.received_at.localeCompare(left.received_at)
        || right.event_id.localeCompare(left.event_id)
      ))[0];
    return {
      attempt_id: attempt.attempt_id,
      invite_token_id: attempt.invite_token,
      token_preview: invite.token_preview || staffInviteTokenPreview(attempt.invite_token),
      email: invite.email || "",
      provider: attempt.provider,
      adapter_idempotency_key: staffInviteDeliveryAdapterIdempotencyKey(attempt),
      attempt_status: attempt.status,
      worker_status: workerStatus,
      worker_attempt_count: Number(attempt.worker_attempt_count || 0),
      next_worker_run_at: nextWorkerRunAt,
      dead_letter_at: attempt.dead_letter_at || null,
      last_worker_error: attempt.last_worker_error || null,
      due: (
        attempt.status === "queued"
        && ["queued", "retry_scheduled"].includes(workerStatus)
        && !attempt.dead_letter_at
        && (dueAt === null || dueAt <= now.getTime())
      ),
      invite_active_pending: activePending,
      last_delivery_event_type: lastEvent?.event_type || null,
    };
  }

  function inviteDeliveryOutbox() {
    const now = new Date();
    const items = demo.staffInviteDeliveryAttempts
      .map((attempt) => staffInviteDeliveryOutboxItem(attempt, now))
      .sort((left, right) => (
        String(left.next_worker_run_at || "z").localeCompare(String(right.next_worker_run_at || "z"))
        || right.attempt_id.localeCompare(left.attempt_id)
      ));
    const queuedCount = items.filter((item) => (
      item.attempt_status === "queued"
      && ["queued", "retry_scheduled"].includes(item.worker_status)
    )).length;
    const dueCount = items.filter((item) => item.due).length;
    const retryScheduledCount = items.filter((item) => item.worker_status === "retry_scheduled").length;
    const deadLetterCount = items.filter((item) => item.worker_status === "dead_letter").length;
    const completedCount = items.filter((item) => item.worker_status === "completed").length;
    return {
      status: dueCount || deadLetterCount ? "attention" : "ok",
      generated_at: now.toISOString(),
      queued_count: queuedCount,
      due_count: dueCount,
      retry_scheduled_count: retryScheduledCount,
      dead_letter_count: deadLetterCount,
      completed_count: completedCount,
      items,
      recommended_action: deadLetterCount
        ? "Review dead-lettered invite delivery attempts, rotate stale links, or configure a real transactional provider before onboarding."
        : dueCount
          ? "Run the invite delivery outbox worker or connect an external delivery provider."
          : "No invite delivery worker action is due.",
      limitation: INVITE_DELIVERY_WORKER_LIMITATION,
    };
  }

  function runInviteDeliveryOutbox(payload = {}, actorEmail = null) {
    const limit = clamp(number(payload.limit, 50), 1, 500);
    const maxAttempts = clamp(number(payload.max_attempts, 3), 1, 10);
    const backoffSeconds = clamp(number(payload.backoff_seconds, 300), 1, 86400);
    const dryRun = Boolean(payload.dry_run);
    const now = new Date();
    const generatedAt = now.toISOString();
    const dueAttempts = demo.staffInviteDeliveryAttempts
      .filter((attempt) => staffInviteDeliveryOutboxItem(attempt, now).due)
      .slice(0, limit);
    const results = [];
    let retryScheduledCount = 0;
    let deadLetteredCount = 0;
    let completedCount = 0;
    let skippedCount = 0;
    dueAttempts.forEach((attempt) => {
      const item = staffInviteDeliveryOutboxItem(attempt, now);
      const previousWorkerStatus = item.worker_status;
      let workerAttemptCount = item.worker_attempt_count;
      const result = {
        attempt_id: attempt.attempt_id,
        invite_token_id: attempt.invite_token,
        provider: attempt.provider,
        adapter_idempotency_key: item.adapter_idempotency_key,
        action: dryRun ? "dry_run" : "skipped",
        previous_worker_status: previousWorkerStatus,
        worker_status: previousWorkerStatus,
        worker_attempt_count: workerAttemptCount,
        next_worker_run_at: item.next_worker_run_at,
        dead_letter_at: item.dead_letter_at,
        error: item.last_worker_error,
      };
      if (dryRun) {
        skippedCount += 1;
        results.push(result);
        return;
      }
      if (!item.invite_active_pending) {
        attempt.worker_status = "completed";
        attempt.next_worker_run_at = null;
        attempt.dead_letter_at = null;
        attempt.last_worker_error = null;
        result.action = "completed";
        result.worker_status = "completed";
        result.next_worker_run_at = null;
        result.dead_letter_at = null;
        result.error = null;
        completedCount += 1;
        results.push(result);
        return;
      }
      workerAttemptCount += 1;
      const workerError = staffInviteDeliveryWorkerError(attempt.provider);
      if (workerAttemptCount >= maxAttempts) {
        attempt.status = "failed";
        attempt.error = workerError;
        attempt.worker_status = "dead_letter";
        attempt.worker_attempt_count = workerAttemptCount;
        attempt.next_worker_run_at = null;
        attempt.dead_letter_at = generatedAt;
        attempt.last_worker_error = workerError;
        result.action = "dead_lettered";
        result.worker_status = "dead_letter";
        result.worker_attempt_count = workerAttemptCount;
        result.next_worker_run_at = null;
        result.dead_letter_at = generatedAt;
        result.error = workerError;
        deadLetteredCount += 1;
      } else {
        const nextWorkerRunAt = new Date(
          now.getTime() + backoffSeconds * (2 ** Math.max(0, workerAttemptCount - 1)) * 1000,
        ).toISOString();
        attempt.status = "queued";
        attempt.error = workerError;
        attempt.worker_status = "retry_scheduled";
        attempt.worker_attempt_count = workerAttemptCount;
        attempt.next_worker_run_at = nextWorkerRunAt;
        attempt.dead_letter_at = null;
        attempt.last_worker_error = workerError;
        result.action = "scheduled_retry";
        result.worker_status = "retry_scheduled";
        result.worker_attempt_count = workerAttemptCount;
        result.next_worker_run_at = nextWorkerRunAt;
        result.dead_letter_at = null;
        result.error = workerError;
        retryScheduledCount += 1;
      }
      results.push(result);
    });
    if (!dryRun) {
      addAudit("staff_invite_delivery_worker_run", "staff_invite_delivery_outbox", `invite-delivery-worker-${Date.now()}`, actorEmail, {
        processed_count: results.length,
        retry_scheduled_count: retryScheduledCount,
        dead_lettered_count: deadLetteredCount,
        completed_count: completedCount,
        skipped_count: skippedCount,
        limit,
        max_attempts: maxAttempts,
        backoff_seconds: backoffSeconds,
        dry_run: dryRun,
        attempt_previews: results.map((result) => staffInviteTokenPreview(result.invite_token_id)),
        adapter_idempotency_keys: results.map((result) => result.adapter_idempotency_key),
      });
    }
    return {
      generated_at: generatedAt,
      dry_run: dryRun,
      processed_count: results.length,
      retry_scheduled_count: retryScheduledCount,
      dead_lettered_count: deadLetteredCount,
      completed_count: completedCount,
      skipped_count: skippedCount,
      results,
      limitation: INVITE_DELIVERY_WORKER_LIMITATION,
    };
  }

  function mfaReadiness(users) {
    const accounts = [];
    let activeStaffCount = 0;
    let mfaAttestedCount = 0;
    let missingMfaCount = 0;
    let disabledStaffCount = 0;
    Object.values(users).forEach((user) => {
      if (!["admin", "mfi_analyst"].includes(user.role)) return;
      const disabled = Boolean(user.disabled_at);
      const mfaAttested = Boolean(user.mfa_attested_at);
      let status = "missing";
      if (disabled) {
        disabledStaffCount += 1;
        status = "disabled";
      } else {
        activeStaffCount += 1;
        if (mfaAttested) {
          mfaAttestedCount += 1;
          status = "ready";
        } else {
          missingMfaCount += 1;
        }
      }
      accounts.push({
        email: user.email,
        role: user.role,
        organization_id: user.organization_id || null,
        disabled,
        mfa_required: !disabled,
        mfa_attested: mfaAttested,
        mfa_attested_at: user.mfa_attested_at || null,
        mfa_method: user.mfa_method || null,
        status,
      });
    });
    return {
      status: missingMfaCount ? "blocked" : "ready",
      active_staff_count: activeStaffCount,
      mfa_attested_count: mfaAttestedCount,
      missing_mfa_count: missingMfaCount,
      disabled_staff_count: disabledStaffCount,
      accounts: accounts.sort((left, right) => `${left.role}:${left.email}`.localeCompare(`${right.role}:${right.email}`)),
      recommended_action: missingMfaCount
        ? "Record MFA attestation for active admin and MFI analyst accounts before pilot use."
        : "All active staff accounts have MFA attestation recorded.",
      limitation: "MFA Readiness v2 records staff attestation and the local prototype requires a second-factor code for staff sessions; it is not a production identity provider.",
    };
  }

  function recordStaffMfaChallengeFailed({
    actorEmail,
    entityType,
    entityId,
    reason,
    source,
    mfaCode,
    method = "prototype_mfa_code",
    details = {},
  }) {
    addAudit("staff_mfa_challenge_failed", entityType, entityId, actorEmail, {
      reason,
      source,
      method,
      prototype: true,
      mfa_code_present: Boolean(String(mfaCode || "").trim()),
      ...details,
    });
  }

  function recentStaffMfaFailures(windowHours = 24) {
    const cutoff = Date.now() - windowHours * 60 * 60 * 1000;
    return demo.auditEvents.filter((event) => (
      event.action === "staff_mfa_challenge_failed"
      && Date.parse(event.created_at) >= cutoff
    ));
  }

  function securityReadiness() {
    const mfa = mfaReadiness(demo.users);
    const inviteHealth = staffInviteHealth(Object.values(demo.staffInvites));
    const checks = [];
    if (mfa.missing_mfa_count) {
      checks.push({
        key: "mfa_attestation",
        label: "Staff MFA attestation",
        status: "blocker",
        summary: `${mfa.missing_mfa_count} active staff account(s) lack MFA attestation.`,
        action: "Record MFA attestation for every active admin and MFI analyst account.",
      });
    } else {
      checks.push({
        key: "mfa_attestation",
        label: "Staff MFA attestation",
        status: "pass",
        summary: "All active staff accounts have MFA attestation recorded.",
        action: "Keep attestation current when staff accounts change.",
      });
    }
    if (inviteHealth.action_required_count) {
      checks.push({
        key: "invite_hygiene",
        label: "Staff invite hygiene",
        status: "blocker",
        summary: `${inviteHealth.action_required_count} pending invite(s) are expired or expiring soon.`,
        action: "Revoke stale invites and create fresh links only when onboarding is active.",
      });
    } else {
      checks.push({
        key: "invite_hygiene",
        label: "Staff invite hygiene",
        status: "pass",
        summary: "No expired or soon-expiring pending staff invites require action.",
        action: "Continue reviewing invite health before pilot access.",
      });
    }
    checks.push({
      key: "session_ttl",
      label: "Session lifetime",
      status: "pass",
      summary: `Current session TTL is ${DEMO_SESSION_TTL_SECONDS} seconds.`,
      action: "Keep reviewer sessions at or below 8 hours.",
    });
    checks.push({
      key: "mfa_enforcement",
      label: "Login-time MFA enforcement",
      status: "pass",
      summary: "Staff login requires an MFA-attested account and a prototype second-factor code.",
      action: "Replace the prototype shared-code control with TOTP/WebAuthn or an external identity provider before real user data.",
    });
    const mfaFailures = recentStaffMfaFailures();
    if (mfaFailures.length) {
      const affectedEntities = new Set(mfaFailures.map((event) => event.entity_id).filter(Boolean));
      checks.push({
        key: "mfa_challenge_failures",
        label: "Recent staff MFA challenge failures",
        status: "warning",
        summary: `${mfaFailures.length} failed staff MFA challenge(s) across ${affectedEntities.size} account/invite target(s) in the last 24 hours.`,
        action: "Review failed MFA audit events before pilot access and rotate credentials if needed.",
      });
    } else {
      checks.push({
        key: "mfa_challenge_failures",
        label: "Recent staff MFA challenge failures",
        status: "pass",
        summary: "No failed staff MFA challenges were recorded in the last 24 hours.",
        action: "Continue monitoring MFA challenge failures in the audit log.",
      });
    }
    const activePendingInvites = Object.values(demo.staffInvites).filter((invite) => (
      !invite.accepted_at
      && !invite.revoked_at
      && Date.parse(invite.expires_at) > Date.now()
    ));
    const undeliveredInvites = activePendingInvites.filter((invite) => !invite.delivered_at);
    const failedDeliveryInvites = activePendingInvites.filter((invite) => {
      const attempts = staffInviteDeliveryAttempts(invite.token_id);
      return !invite.delivered_at && attempts[0]?.status === "failed";
    });
    const unsafeDeliveredInvites = activePendingInvites.filter((invite) => (
      invite.delivered_at
      && !String(invite.delivery_url_base || "").startsWith("https://")
      && !String(invite.delivery_url_base || "").startsWith("http://127.0.0.1")
      && !String(invite.delivery_url_base || "").startsWith("http://localhost")
    ));
    if (undeliveredInvites.length) {
      checks.push({
        key: "invite_delivery",
        label: "Invite delivery and HTTPS links",
        status: "blocker",
        summary: `${undeliveredInvites.length} active pending staff invite(s) lack audited delivery metadata.`,
        action: "Record invite delivery before sharing onboarding links.",
      });
    } else if (unsafeDeliveredInvites.length) {
      checks.push({
        key: "invite_delivery",
        label: "Invite delivery and HTTPS links",
        status: "blocker",
        summary: `${unsafeDeliveredInvites.length} delivered staff invite(s) use a non-HTTPS, non-local URL base.`,
        action: "Use HTTPS invite URLs outside local development.",
      });
    } else {
      checks.push({
        key: "invite_delivery",
        label: "Invite delivery and HTTPS links",
        status: "pass",
        summary: activePendingInvites.length
          ? "All active pending staff invites have audited delivery metadata."
          : "No active pending staff invites require delivery.",
        action: "Use audited delivery records and move to transactional email before production onboarding.",
      });
    }
    if (failedDeliveryInvites.length) {
      checks.push({
        key: "invite_delivery_attempts",
        label: "Invite delivery provider attempts",
        status: "warning",
        summary: `${failedDeliveryInvites.length} active pending staff invite(s) have a failed latest delivery attempt.`,
        action: "Retry invite delivery with a working provider, or rotate/revoke stale links.",
      });
    } else {
      checks.push({
        key: "invite_delivery_attempts",
        label: "Invite delivery provider attempts",
        status: "pass",
        summary: "No active pending staff invite has a failed latest delivery attempt.",
        action: "Monitor delivery attempts and retry failures before sharing onboarding links.",
      });
    }
    const blockers = checks.filter((check) => check.status === "blocker");
    const warnings = checks.filter((check) => check.status === "warning");
    return {
      status: blockers.length ? "blocked" : warnings.length ? "review" : "ready",
      generated_at: nowIso(),
      blockers_count: blockers.length,
      warnings_count: warnings.length,
      checks,
      recommended_actions: checks
        .filter((check) => check.status !== "pass")
        .map((check) => check.action),
      limitation: "Security Readiness v1 is a pre-pilot control summary for the local prototype; MFA enforcement uses a local prototype code and is not a completed production security review.",
    };
  }

  function readinessSeverity(status) {
    if (status === "blocker") return "blocker";
    if (status === "warning") return "warning";
    return "pass";
  }

  function identityReadiness(session = {}) {
    const mfa = mfaReadiness(demo.users);
    const deliveryReadiness = inviteDeliveryReadiness();
    const activeSessions = activeStaffSessions(session.token);
    const inviteDeliveryStatus = deliveryReadiness.status === "blocked" ? "blocker" : "warning";
    const mfaStatus = mfa.missing_mfa_count ? "blocker" : "warning";
    const sessionStatus = activeSessions.some((row) => !row.session_id || row.token)
      ? "blocker"
      : "pass";
    const tenantCount = Object.keys(demo.organizations).length;
    const components = [
      {
        key: "auth_provider",
        label: "Authentication provider",
        severity: "blocker",
        status: "blocker",
        summary: "Static demo staff authentication uses local password accounts managed inside the prototype API.",
        action: "Replace with a production IdP, TOTP/WebAuthn enrollment, recovery, and audit-backed admin policies before real borrower data.",
      },
      {
        key: "invite_delivery",
        label: "Invite delivery evidence",
        severity: readinessSeverity(inviteDeliveryStatus),
        status: inviteDeliveryStatus,
        summary: `Invite delivery provider is '${deliveryReadiness.configured_provider}' with URL base '${deliveryReadiness.invite_url_base}'; delivery readiness is ${deliveryReadiness.status}.`,
        action: deliveryReadiness.next_required_controls[0]?.action
          || "Move staff invite delivery to transactional email or approved secure messaging.",
      },
      {
        key: "mfa_posture",
        label: "MFA posture",
        severity: readinessSeverity(mfaStatus),
        status: mfaStatus,
        summary: `${mfa.mfa_attested_count} attested active staff account(s); ${mfa.missing_mfa_count} active staff account(s) missing attestation.`,
        action: mfaStatus === "blocker"
          ? "Record MFA attestation for every active staff account."
          : "Replace prototype-code MFA with IdP-backed TOTP/WebAuthn before real staff onboarding.",
      },
      {
        key: "session_control",
        label: "Session inventory and revoke",
        severity: sessionStatus === "pass" ? "info" : "blocker",
        status: sessionStatus,
        summary: `${activeSessions.length} active staff session(s); session previews and hashed ids are exposed without raw bearer tokens.`,
        action: "Continue using targeted revocation and the current-admin self-revoke guard.",
      },
      {
        key: "rate_limit",
        label: "Login rate limiting",
        severity: "blocker",
        status: "blocker",
        summary: "Static demo login throttling is local/in-process and does not protect a distributed deployment.",
        action: "Move rate limiting to the external IdP, Redis, or managed edge controls before production.",
      },
      {
        key: "tenant_isolation",
        label: "Tenant isolation evidence",
        severity: "info",
        status: "pass",
        summary: `${tenantCount} organization record(s); MFI queues, analytics, exports, review packets, and simulations are scoped by organization_id in the static contract.`,
        action: "Keep organization_id scoped when adding new reviewer surfaces.",
      },
      {
        key: "storage_backend",
        label: "Storage readiness",
        severity: "blocker",
        status: "blocker",
        summary: "Static demo mirrors SQLite development persistence and does not claim encrypted production storage, backups, or managed database controls.",
        action: "Move real pilot data to managed PostgreSQL with backups, retention, access logging, and secret management.",
      },
    ];
    const blockers = components.filter((row) => row.status === "blocker");
    const warnings = components.filter((row) => row.status === "warning");
    const nextRequiredControls = blockers.concat(warnings).map((row) => ({
      key: row.key,
      severity: row.status === "blocker" ? "blocker" : "warning",
      summary: row.summary,
      action: row.action,
    }));
    return {
      status: blockers.length ? "blocked" : warnings.length ? "review" : "ready",
      generated_at: nowIso(),
      auth_provider_mode: "local_password_prototype",
      invite_delivery_mode: "static_demo_local_delivery",
      mfa_mode: "prototype_shared_code_with_admin_attestation",
      session_control_mode: "local_bearer_sessions_with_admin_revoke",
      rate_limit_mode: "in_memory_single_process",
      storage_backend: "sqlite_static_demo",
      tenant_isolation_mode: "organization_id_scoped_mfi_access",
      active_staff_count: mfa.active_staff_count,
      active_staff_session_count: activeSessions.length,
      active_pending_invite_count: deliveryReadiness.active_pending_invite_count,
      components,
      production_blockers: blockers.map((row) => ({
        key: row.key,
        severity: "blocker",
        summary: row.summary,
        action: row.action,
      })),
      next_required_controls: nextRequiredControls,
      limitation: "Identity Readiness v1 is reviewer-facing prototype evidence. It is not a completed production security review and does not certify production readiness, identity provider maturity, encrypted storage, or permission to collect real borrower data.",
    };
  }

  function prePilotCheckStatus(status) {
    if (["blocked", "blocker", "missing", "invalid"].includes(status)) return "blocker";
    if (["review", "warning", "planned"].includes(status)) return "warning";
    return "pass";
  }

  function postgresqlMigrationReadiness() {
    const jsonColumnCount = POSTGRESQL_SCHEMA_INVENTORY
      .reduce((total, table) => total + table.json_columns.length, 0);
    const tenantScopeCount = POSTGRESQL_SCHEMA_INVENTORY
      .reduce((total, table) => total + table.tenant_scope_columns.length, 0);
    const blockers = [
      {
        key: "postgresql_repository_backend_not_implemented",
        severity: "blocker",
        summary: "The runtime repository backend is still SQLite-only.",
        action: "Implement and test a PostgreSQL repository backend before real pilot data.",
      },
      {
        key: "postgresql_disposable_parity_ci_missing",
        severity: "blocker",
        summary: "CI applies the migration draft, but does not run repository parity tests against PostgreSQL yet.",
        action: "Implement the PostgreSQL repository backend, then run the existing API/database contract tests against disposable PostgreSQL before enabling the backend.",
      },
      {
        key: "postgresql_database_url_missing",
        severity: "blocker",
        summary: "PostgreSQL connection environment is not configured (MICROSCORE_DATABASE_URL).",
        action: "Configure managed database connection secrets without exposing their values.",
      },
    ];
    const presentArtifacts = POSTGRESQL_MIGRATION_ARTIFACTS.filter((artifact) => artifact.present);
    const versionedMigrationContractPresent = presentArtifacts.length > 0
      && presentArtifacts[0].table_count === POSTGRESQL_SCHEMA_INVENTORY.length
      && presentArtifacts[0].jsonb_column_count === jsonColumnCount
      && presentArtifacts[0].tenant_scope_index_count === 4;
    return {
      status: "blocked",
      generated_at: nowIso(),
      runtime_backend: "sqlite",
      target_backend: "postgresql",
      repository_backend_status: "not_implemented",
      migration_ready: false,
      production_ready: false,
      live_connection_tested: false,
      required_environment: ["MICROSCORE_DATABASE_URL"],
      configured_environment: [],
      missing_environment: ["MICROSCORE_DATABASE_URL"],
      required_table_count: POSTGRESQL_SCHEMA_INVENTORY.length,
      present_table_count: POSTGRESQL_SCHEMA_INVENTORY.filter((table) => table.present_in_sqlite).length,
      json_column_count: jsonColumnCount,
      tenant_scope_count: tenantScopeCount,
      migration_artifact_count: presentArtifacts.length,
      latest_migration_version: presentArtifacts[0]?.version || null,
      versioned_migration_contract_present: versionedMigrationContractPresent,
      disposable_migration_ci_present: true,
      repository_adapter_contract_status: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.status,
      repository_adapter_contract_present: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.present,
      repository_adapter_contract_version: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.version,
      repository_adapter_module: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.module,
      repository_adapter_stage: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.stage,
      repository_adapter_contract_method_count: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.method_count,
      repository_adapter_implemented_method_count: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.implemented_method_count,
      repository_adapter_pending_method_count: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.pending_method_count,
      repository_adapter_read_only_method_count: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.read_only_method_count,
      repository_adapter_write_method_count: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.write_method_count,
      repository_adapter_completed_method_group_count: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.completed_method_group_count,
      repository_adapter_completed_method_groups: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.completed_method_groups,
      repository_adapter_implemented_methods: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.implemented_methods,
      repository_adapter_model_registry_read_present: true,
      repository_adapter_model_registry_write_present: true,
      repository_adapter_model_registry_group_present: true,
      repository_adapter_contract_groups: POSTGRESQL_REPOSITORY_ADAPTER_CONTRACT.method_groups,
      migration_artifacts: POSTGRESQL_MIGRATION_ARTIFACTS,
      schema_inventory: POSTGRESQL_SCHEMA_INVENTORY,
      parity_checks: [
        {
          key: "postgresql_schema_inventory",
          status: "pass",
          sqlite_evidence: `${POSTGRESQL_SCHEMA_INVENTORY.length}/${POSTGRESQL_SCHEMA_INVENTORY.length} required SQLite tables are present.`,
          postgres_requirement: "Every required table has an explicit PostgreSQL migration.",
          action: "Keep generated migration inventory in review.",
        },
        {
          key: "postgresql_versioned_migration_artifacts",
          status: versionedMigrationContractPresent ? "pass" : "blocker",
          sqlite_evidence: `${presentArtifacts.length}/1 expected migration artifact(s) are present.`,
          postgres_requirement: "A versioned SQL migration must cover every required table, JSONB column, and tenant-scope index.",
          action: versionedMigrationContractPresent
            ? "Keep migrations/postgresql/0001_initial_schema.sql in review until a live PostgreSQL runner exists."
            : "Create a complete migrations/postgresql/0001_initial_schema.sql artifact.",
        },
        {
          key: "postgresql_jsonb_mapping",
          status: "pass",
          sqlite_evidence: `${jsonColumnCount} JSON text column(s) are used by SQLite.`,
          postgres_requirement: "Map JSON text columns to jsonb or a versioned text strategy.",
          action: "The initial PostgreSQL migration draft maps SQLite JSON text columns to JSONB.",
        },
        {
          key: "postgresql_tenant_scope_parity",
          status: "planned",
          sqlite_evidence: `${tenantScopeCount} tenant-scope column(s) are tracked; 4/4 tenant index draft(s) are present.`,
          postgres_requirement: "Preserve organization_id scoping in indexes, repository queries, and optional row-level security.",
          action: "Review tenant indexes in the draft migration and add repository parity tests for MFI queues, analytics, review packets, invites, and simulations.",
        },
        {
          key: "postgresql_disposable_migration_ci",
          status: "pass",
          sqlite_evidence: "CI applies the draft migration to a disposable PostgreSQL service.",
          postgres_requirement: "Every versioned migration must be executed against a fresh PostgreSQL database before pilot storage work proceeds.",
          action: "Keep scripts/postgresql-migration-smoke.py and the postgres:16 CI service as the migration smoke gate.",
        },
        {
          key: "postgresql_repository_adapter_contract",
          status: "pass",
          sqlite_evidence: "52 SQLite repository method(s) are grouped into adapter contract families; 5 method(s) currently have PostgreSQL adapter coverage.",
          postgres_requirement: "A PostgreSQL adapter must implement the same repository method families before backend selection can be enabled.",
          action: "Keep microscore_api.postgres_repository as the incremental adapter surface until every method family is implemented and parity-tested.",
        },
        {
          key: "postgresql_model_registry_read_adapter",
          status: "pass",
          sqlite_evidence: "3 read-only model registry method(s) have PostgreSQL query specs and a SQLite-vs-adapter parity snapshot harness.",
          postgres_requirement: "The adapter must read model_versions with PostgreSQL boolean and JSONB semantics before model governance can move off SQLite.",
          action: "Keep read parity covered while promoting the complete model registry group into disposable PostgreSQL CI.",
        },
        {
          key: "postgresql_model_registry_method_group_adapter",
          status: "pass",
          sqlite_evidence: "5 model registry method(s) have PostgreSQL query specs and SQLite-vs-adapter parity coverage, including 2 write method(s).",
          postgres_requirement: "The adapter must preserve model version creation, active-version atomicity, PostgreSQL boolean handling, and JSONB materialization.",
          action: "Promote the complete model registry adapter group into disposable PostgreSQL repository CI, then start the next tenant-scoped method group.",
        },
        {
          key: "postgresql_repository_backend",
          status: "blocker",
          sqlite_evidence: "Runtime repository supports sqlite only and rejects postgresql at startup; the adapter has a complete model registry method group but does not yet cover the full repository contract.",
          postgres_requirement: "Implement a PostgreSQL repository backend behind the same API contract.",
          action: "Expand the PostgreSQL adapter from model registry to tenant-scoped queues, applications, simulations, analytics, identity, and audit flows.",
        },
        {
          key: "postgresql_disposable_ci",
          status: "blocker",
          sqlite_evidence: "CI applies the migration draft to disposable PostgreSQL, but repository parity cannot run until a PostgreSQL backend exists.",
          postgres_requirement: "Run parity tests against a disposable PostgreSQL database in CI.",
          action: "Implement the PostgreSQL repository backend, then promote this migration smoke into backend parity tests.",
        },
      ],
      blockers,
      next_required_controls: blockers,
      limitation: POSTGRESQL_READINESS_LIMITATION,
    };
  }

  function prePilotReadiness(session = {}) {
    const security = securityReadiness();
    const identity = identityReadiness(session);
    const delivery = inviteDeliveryReadiness();
    const adapter = inviteDeliveryAdapterReadiness();
    const postgresql = postgresqlMigrationReadiness();
    const activeModel = activeModelVersion();
    const scored = demo.applications.filter((app) => app.score_result);
    const decided = demo.applications.filter((app) => app.decision_result);
    const latestSimulation = demo.simulations[0] || null;
    const latestScenarios = new Set((latestSimulation?.scenarios || []).map((row) => row.scenario));
    const hasCoreSimulationScenarios = ["baseline", "adverse", "severe"]
      .every((scenario) => latestScenarios.has(scenario));
    const modelLimitations = activeModel?.limitations || [];
    const checks = [
      {
        key: "security_readiness",
        label: "Security readiness gate",
        category: "security",
        status: prePilotCheckStatus(security.status),
        summary: `Security readiness is ${security.status} with ${security.blockers_count} blocker(s) and ${security.warnings_count} warning(s).`,
        action: security.recommended_actions[0] || "Keep security readiness checks in the release gate.",
        evidence: {
          status: security.status,
          blockers_count: security.blockers_count,
          warnings_count: security.warnings_count,
          check_keys: security.checks.map((check) => check.key),
        },
      },
      {
        key: "identity_provider",
        label: "Production identity and access",
        category: "identity",
        status: prePilotCheckStatus(identity.status),
        summary: `Identity readiness is ${identity.status}; ${identity.production_blockers.length} production blocker(s) remain.`,
        action: identity.next_required_controls[0]?.action || "Keep identity evidence current before pilot access.",
        evidence: {
          auth_provider_mode: identity.auth_provider_mode,
          mfa_mode: identity.mfa_mode,
          session_control_mode: identity.session_control_mode,
          rate_limit_mode: identity.rate_limit_mode,
          production_blocker_keys: identity.production_blockers.map((item) => item.key),
        },
      },
      {
        key: "transactional_delivery_adapter",
        label: "Transactional invite delivery",
        category: "delivery",
        status: prePilotCheckStatus(adapter.status),
        summary: `Delivery adapter is ${adapter.status}; external_send_enabled=${adapter.external_send_enabled} and send_adapter_ready=${adapter.send_adapter_ready}.`,
        action: adapter.next_required_controls[0]?.action || "Keep the adapter boundary blocked until a production sender exists.",
        evidence: {
          provider: adapter.provider,
          adapter_mode: adapter.adapter_mode,
          configuration_status: adapter.configuration_status,
          secret_rotation_ready: adapter.secret_rotation_ready,
          blocker_keys: adapter.blockers.map((item) => item.key),
          safe_payload_fields: adapter.safe_payload_fields,
          forbidden_payload_fields: adapter.forbidden_payload_fields,
        },
      },
      {
        key: "invite_delivery_evidence",
        label: "Audited invite delivery evidence",
        category: "delivery",
        status: prePilotCheckStatus(delivery.status),
        summary: `Invite delivery readiness is ${delivery.status} using '${delivery.configured_provider}'; ${delivery.undelivered_active_invite_count} active pending invite(s) lack delivery evidence.`,
        action: delivery.next_required_controls[0]?.action || "Continue recording audited invite delivery attempts.",
        evidence: {
          configured_provider: delivery.configured_provider,
          invite_url_https: delivery.invite_url_https,
          invite_url_local: delivery.invite_url_local,
          active_pending_invite_count: delivery.active_pending_invite_count,
          undelivered_active_invite_count: delivery.undelivered_active_invite_count,
          failed_latest_attempt_count: delivery.failed_latest_attempt_count,
        },
      },
      {
        key: "storage_backend",
        label: "Production storage backend",
        category: "storage",
        status: "blocker",
        summary: `Storage backend is 'sqlite_static_demo'; PostgreSQL readiness is ${postgresql.status} with ${postgresql.blockers.length} blocker(s).`,
        action: postgresql.next_required_controls[0]?.action || "Complete PostgreSQL migration readiness, backups, retention, and disposable integration tests.",
        evidence: {
          backend: "sqlite_static_demo",
          production_ready: false,
          postgresql_migration_status: "planned",
          postgresql_readiness_status: postgresql.status,
          postgresql_repository_backend_status: postgresql.repository_backend_status,
          postgresql_schema_inventory_table_count: postgresql.present_table_count,
          postgresql_parity_check_count: postgresql.parity_checks.length,
          postgresql_migration_artifact_count: postgresql.migration_artifact_count,
          postgresql_latest_migration_version: postgresql.latest_migration_version,
          postgresql_versioned_migration_contract_present: postgresql.versioned_migration_contract_present,
          postgresql_disposable_migration_ci_present: postgresql.disposable_migration_ci_present,
          postgresql_repository_adapter_contract_status: postgresql.repository_adapter_contract_status,
          postgresql_repository_adapter_contract_method_count: postgresql.repository_adapter_contract_method_count,
          postgresql_repository_adapter_implemented_method_count: postgresql.repository_adapter_implemented_method_count,
          postgresql_repository_adapter_completed_method_group_count: postgresql.repository_adapter_completed_method_group_count,
          postgresql_repository_adapter_completed_method_groups: postgresql.repository_adapter_completed_method_groups,
          postgresql_repository_adapter_stage: postgresql.repository_adapter_stage,
          postgresql_blocker_keys: postgresql.blockers.map((item) => item.key),
          tenant_scoped_tables: [
            "users.organization_id",
            "loan_applications.organization_id",
            "staff_invites.organization_id",
            "portfolio_simulations.organization_id",
          ],
        },
      },
      {
        key: "model_registry",
        label: "Model registry and validation boundary",
        category: "model",
        status: !activeModel
          ? "blocker"
          : modelLimitations.some((item) => /synthetic|not validated/i.test(item))
            ? "warning"
            : "pass",
        summary: activeModel
          ? `Active model '${activeModel.version}' is registered with ${modelLimitations.length} limitation(s).`
          : "No active model version is registered.",
        action: activeModel
          ? "Replace synthetic-only validation with permitted MFI/KZT calibration evidence before real pilot decisions."
          : "Register and activate a reviewed model version before scoring.",
        evidence: {
          active_model_version: activeModel?.version || null,
          registered_model_count: Object.keys(demo.modelVersions).length,
          feature_schema_version: activeModel?.feature_schema_version || null,
          training_data_label: activeModel?.training_data_label || null,
        },
      },
      {
        key: "monte_carlo_evidence",
        label: "Monte Carlo portfolio stress evidence",
        category: "simulation",
        status: hasCoreSimulationScenarios ? "pass" : "warning",
        summary: hasCoreSimulationScenarios
          ? "Latest saved Monte Carlo run includes baseline/adverse/severe scenarios."
          : "No saved Monte Carlo run with baseline/adverse/severe scenarios is available for the current release evidence.",
        action: hasCoreSimulationScenarios
          ? "Keep seeded simulations reproducible and clearly labeled as scenario planning."
          : "Run and save a seeded baseline/adverse/severe simulation before a reviewer demo.",
        evidence: {
          simulation_count: demo.simulations.length,
          latest_simulation_id: latestSimulation?.simulation_id || null,
          latest_scenarios: [...latestScenarios].sort(),
          latest_warning_count: latestSimulation?.warnings?.length ?? null,
        },
      },
      {
        key: "review_flow_evidence",
        label: "Borrower-to-analyst review flow",
        category: "demo",
        status: scored.length ? "pass" : "warning",
        summary: `${demo.applications.length} application(s), ${scored.length} scored application(s), and ${decided.length} recorded analyst decision(s) are present.`,
        action: scored.length
          ? "Keep borrower-safe status and MFI review packet smokes in the release gate."
          : "Submit and score a synthetic application before a reviewer demo.",
        evidence: {
          application_count: demo.applications.length,
          scored_application_count: scored.length,
          decided_application_count: decided.length,
        },
      },
      {
        key: "privacy_data_boundary",
        label: "Minimum-data and sensitive-field boundary",
        category: "privacy",
        status: "pass",
        summary: "Pilot data classes and forbidden data remain explicit; application intake requires consent and rejects secret-bearing/sensitive fields.",
        action: "Keep legal/privacy review ahead of any real borrower data collection.",
        evidence: {
          data_class_count: 5,
          forbidden_data_count: 7,
          consent_required: true,
          sensitive_field_rejection: true,
        },
      },
      {
        key: "tenant_isolation",
        label: "Organization-scoped MFI access",
        category: "tenant",
        status: "pass",
        summary: `${Object.keys(demo.organizations).length} organization record(s); queues, review packets, analytics, simulations, and staff invites remain organization-scoped.`,
        action: "Keep organization_id guards on every new MFI/admin surface.",
        evidence: {
          organization_count: Object.keys(demo.organizations).length,
          tenant_scoped_tables: [
            "users.organization_id",
            "loan_applications.organization_id",
            "staff_invites.organization_id",
            "portfolio_simulations.organization_id",
          ],
        },
      },
    ];
    const blockers = checks.filter((check) => check.status === "blocker");
    const warnings = checks.filter((check) => check.status === "warning");
    const passes = checks.filter((check) => check.status === "pass");
    const status = blockers.length ? "blocked" : warnings.length ? "review" : "ready";
    return {
      status,
      generated_at: nowIso(),
      region: "Pavlodar region, Kazakhstan",
      release_target: PRE_PILOT_RELEASE_TARGET,
      blockers_count: blockers.length,
      warnings_count: warnings.length,
      passes_count: passes.length,
      readiness_score: Math.max(0, Math.min(100, 100 - blockers.length * 15 - warnings.length * 7)),
      production_data_allowed: !blockers.length && !warnings.length,
      public_demo_allowed: Boolean(activeModel && scored.length),
      checks,
      next_required_controls: blockers.concat(warnings).map((check) => ({
        key: check.key,
        severity: check.status === "blocker" ? "blocker" : "warning",
        summary: check.summary,
        action: check.action,
      })),
      signed_off_capabilities: passes.map((check) => check.label),
      blocked_capabilities: blockers.map((check) => check.label),
      limitation: PRE_PILOT_READINESS_LIMITATION,
    };
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function parseBody(options) {
    if (!options?.body) return {};
    return typeof options.body === "string" ? JSON.parse(options.body) : options.body;
  }

  function resetDemo() {
    demo.users = {};
    demo.organizations = {
      "pavlodar-demo-mfi": {
        id: "pavlodar-demo-mfi",
        name: "Pavlodar Demo MFI",
        region: "Pavlodar region, Kazakhstan",
        created_at: nowIso(),
      },
    };
    demo.applications = [];
    demo.decisions = {};
    demo.simulations = [];
    demo.staffInvites = {};
    demo.staffInviteSecrets = {};
    demo.staffInviteDeliveryAttempts = [];
    demo.staffInviteDeliveryEvents = [];
    demo.modelVersions = {
      "static-demo-v1": {
        version: "static-demo-v1",
        model_name: "Logistic Regression",
        model_type: "logistic_regression",
        lifecycle_status: "active",
        is_active: true,
        feature_schema_version: "behavioral-v1",
        training_data_label: "synthetic-demo-portfolio-v1",
        random_state: 42,
        metrics: { roc_auc: 0.8063, brier_score: 0.1855 },
        limitations: ["Synthetic validation only.", "Human review is required."],
        created_by: "system",
        created_at: nowIso(),
        activated_at: nowIso(),
      },
      "static-demo-v2-candidate": {
        version: "static-demo-v2-candidate",
        model_name: "Logistic Regression",
        model_type: "logistic_regression",
        lifecycle_status: "candidate",
        is_active: false,
        feature_schema_version: "behavioral-v2",
        training_data_label: "synthetic-demo-portfolio-v2",
        random_state: 77,
        metrics: { roc_auc: 0.821, brier_score: 0.176 },
        limitations: ["Candidate uses synthetic validation only."],
        created_by: "admin@test.com",
        created_at: nowIso(),
        activated_at: null,
      },
    };
    demo.timelines = {};
    demo.auditEvents = [];
    demo.nextTimelineId = 1;
    demo.nextAuditId = 1;
    demo.nextDecisionId = 1;
    demo.nextApplicationNumber = 1;

    demoUsers.forEach(([email, role, organizationId]) => {
      const staff = ["admin", "mfi_analyst"].includes(role);
      demo.users[email] = {
        email,
        role,
        organization_id: organizationId,
        password: "password123",
        created_at: nowIso(),
        disabled_at: null,
        disabled_by: null,
        mfa_attested_at: staff ? nowIso() : null,
        mfa_attested_by: staff ? (role === "admin" ? email : "admin@test.com") : null,
        mfa_method: staff ? "prototype_mfa_code" : null,
      };
    });

    seedApplications.forEach((seed, index) => {
      const app = createApplicationRecord(seed, seed.borrower_email, `static-demo-${index + 1}`);
      app.score_result = buildScore(app);
      app.status = "scored";
      app.scored_at = nowIso();
      addTimeline(app.id, "application_scored", "analyst@test.com", {
        model_version: app.score_result.model_version,
        risk_band: app.score_result.risk_band,
      });
      if (seed.decision) {
        app.decision_result = createDecision(app.id, "analyst@test.com", {
          decision: seed.decision,
          policy_name: "balanced_review",
          note: seed.decision_note || "",
        });
        app.status = decisionWorkflowStatuses[seed.decision];
        addTimeline(app.id, "application_decision_recorded", "analyst@test.com", {
          decision: seed.decision,
          policy_name: "balanced_review",
          previous_status: "scored",
          status: app.status,
        });
      }
      demo.applications.push(app);
    });
  }

  function createApplicationRecord(payload, borrowerEmail, id = null) {
    const behavioral = { ...(payload.behavioral_signals || {}) };
    [
      "annual_income",
      "total_outstanding_debt",
      "mobile_banking_logins",
      "online_transfer_frequency",
      "atm_withdrawal_frequency",
      "avg_deposit_amount",
      "debit_card_spending",
      "num_open_loans",
      "late_payment_count",
      "gender",
      "employment_status",
    ].forEach((key) => {
      if (payload[key] !== undefined) behavioral[key] = payload[key];
    });

    behavioral.loan_application_amount = payload.requested_amount;
    if (payload.district) behavioral.pavlodar_district = payload.district;
    if (payload.settlement_type) behavioral.settlement_type = payload.settlement_type;

    const application = {
      id: id || `static-demo-new-${demo.nextApplicationNumber++}`,
      borrower_email: borrowerEmail,
      status: "submitted",
      requested_amount: payload.requested_amount,
      purpose: payload.purpose || "",
      district: payload.district || null,
      settlement_type: payload.settlement_type || null,
      organization_id: payload.organization_id || "pavlodar-demo-mfi",
      behavioral_signals: behavioral,
      score_result: null,
      decision_result: null,
      created_at: nowIso(),
      scored_at: null,
    };
    demo.timelines[application.id] = [];
    demo.decisions[application.id] = [];
    addTimeline(application.id, "application_created", borrowerEmail, {
      requested_amount: payload.requested_amount,
      district: payload.district || "unknown",
    });
    return application;
  }

  function activeModelVersion() {
    return Object.values(demo.modelVersions).find((model) => model.is_active) || null;
  }

  function addTimeline(applicationId, action, actorEmail, details = {}) {
    const event = {
      id: demo.nextTimelineId++,
      action,
      title: timelineTitle(action, details),
      actor_email: actorEmail,
      details,
      created_at: nowIso(),
    };
    demo.timelines[applicationId] = demo.timelines[applicationId] || [];
    demo.timelines[applicationId].push(event);
    return event;
  }

  function addAudit(action, entityType, entityId, actorEmail, details = {}) {
    const event = {
      id: demo.nextAuditId++,
      actor_email: actorEmail,
      action,
      entity_type: entityType,
      entity_id: entityId,
      details,
      created_at: nowIso(),
    };
    demo.auditEvents.unshift(event);
    return event;
  }

  function timelineTitle(action, details = {}) {
    if (action === "application_decision_recorded") {
      const decisionTitles = {
        review: "Application moved to manual review",
        approve: "Application approved",
        decline: "Application declined",
      };
      if (decisionTitles[details.decision]) return decisionTitles[details.decision];
    }
    const titles = {
      application_created: "Application submitted",
      application_scored: "Risk score generated",
      application_rescored: "Risk score refreshed",
      application_decision_recorded: "Analyst decision recorded",
    };
    return titles[action] || action.replaceAll("_", " ");
  }

  function riskBand(probability) {
    if (probability >= 0.58) return "high";
    if (probability >= 0.34) return "medium";
    return "low";
  }

  function factor(feature, value, direction, label = null) {
    return {
      feature,
      value,
      abs_value: Math.abs(value),
      direction,
      label: label || feature,
    };
  }

  function buildScore(application) {
    const activeModel = activeModelVersion();
    if (!activeModel) throw new Error("Scoring is disabled until an administrator activates a model version");
    const s = application.behavioral_signals || {};
    const income = number(s.annual_income, 1);
    const debt = number(s.total_outstanding_debt);
    const late = number(s.late_payment_count);
    const openLoans = number(s.num_open_loans);
    const digitalActivity = number(s.mobile_banking_logins) + number(s.online_transfer_frequency);
    const debtRatio = income ? debt / income : 0.5;
    const ruralRisk = application.settlement_type === "rural" ? 0.06 : 0;
    const districtRisk = ["Akkuly", "Bayanaul", "Uspenka", "Zhelezinka"].includes(application.district) ? 0.04 : 0;
    const digitalProtection = clamp(digitalActivity / 120, 0, 0.18);
    const probability = clamp(
      0.22 + late * 0.16 + debtRatio * 0.48 + openLoans * 0.035 + ruralRisk + districtRisk - digitalProtection,
      0.04,
      0.92,
    );
    const proxyDelta = clamp(late * 0.11, 0, 0.38);
    const thinFileProbability = clamp(probability - proxyDelta + 0.03, 0.04, 0.92);
    const regionalNeutralProbability = clamp(probability - ruralRisk - districtRisk, 0.04, 0.92);
    const band = riskBand(probability);

    const positiveFactors = [
      factor("late_payment_count", late * 0.48, "raises_risk", "Late payments"),
      factor("debt_to_income_ratio", debtRatio * 0.42, "raises_risk", "Debt to income"),
      factor("num_open_loans", openLoans * 0.08, "raises_risk", "Open loans"),
      factor("regional_access_context", ruralRisk + districtRisk, "raises_risk", "Regional access context"),
    ].filter((item) => item.value > 0);
    const protectiveFactors = [
      factor("mobile_banking_logins", -number(s.mobile_banking_logins) * 0.012, "lowers_risk", "Mobile banking use"),
      factor("online_transfer_frequency", -number(s.online_transfer_frequency) * 0.014, "lowers_risk", "Online transfers"),
      factor("avg_deposit_amount", -clamp(number(s.avg_deposit_amount) / 10000, 0, 0.22), "lowers_risk", "Average deposits"),
    ].filter((item) => item.value < 0);

    return {
      model_name: activeModel.model_name,
      model_version: activeModel.version,
      model_governance: {
        lifecycle_status: activeModel.lifecycle_status,
        feature_schema_version: activeModel.feature_schema_version,
        training_data_label: activeModel.training_data_label,
        random_state: activeModel.random_state,
        activated_at: activeModel.activated_at,
        limitations: [...activeModel.limitations],
      },
      high_risk_probability: probability,
      risk_band: band,
      proxy_sensitivity_delta: proxyDelta,
      scenario_scores: [
        {
          scenario: "full_feature_demo",
          label: "Standard demo score",
          high_risk_probability: probability,
          risk_band: band,
          notes: ["Uses synthetic demo features."],
        },
        {
          scenario: "thin_file_without_late_payment_count",
          label: "Thin-file stress test",
          high_risk_probability: thinFileProbability,
          risk_band: riskBand(thinFileProbability),
          notes: ["Removes the strongest proxy-style signal."],
        },
        {
          scenario: "regional_neutral",
          label: "Regional neutral check",
          high_risk_probability: regionalNeutralProbability,
          risk_band: riskBand(regionalNeutralProbability),
          notes: ["Removes regional access assumptions."],
        },
      ],
      decision_support: decisionSupport(probability, proxyDelta, band),
      missing_feature_count: 0,
      missing_features_preview: [],
      explanation: {
        method: "static demo additive scorecard",
        baseline_log_odds: 0,
        total_contribution: probability - 0.22,
        predicted_log_odds: probability,
        high_risk_probability: probability,
        top_positive_factors: positiveFactors.slice(0, 4),
        top_protective_factors: protectiveFactors.slice(0, 4),
        top_factors: [...positiveFactors, ...protectiveFactors]
          .sort((left, right) => right.abs_value - left.abs_value)
          .slice(0, 6),
      },
      top_model_factors: [...positiveFactors, ...protectiveFactors]
        .sort((left, right) => right.abs_value - left.abs_value)
        .slice(0, 6),
      warnings: [
        "Static demo mode uses synthetic data only.",
        "late_payment_count is treated as a proxy-sensitive signal in this demo.",
      ],
    };
  }

  function decisionSupport(probability, proxyDelta, band) {
    if (proxyDelta >= 0.2) {
      return {
        recommendation_code: "manual_review_proxy_sensitive",
        title: "Manual review before decision",
        rationale: ["Risk estimate is sensitive to late-payment history.", "Avoid automatic decline from one proxy-heavy signal."],
        next_steps: ["Ask for payment context.", "Check affordability and income stability."],
      };
    }
    if (band === "high") {
      return {
        recommendation_code: "manual_review_high_risk",
        title: "Senior review recommended",
        rationale: ["Predicted risk is high in the demo scorecard."],
        next_steps: ["Consider smaller starter loan.", "Request additional repayment evidence."],
      };
    }
    if (probability <= 0.25) {
      return {
        recommendation_code: "starter_loan_eligible",
        title: "Starter loan candidate",
        rationale: ["Low demo risk estimate and visible digital activity."],
        next_steps: ["Verify identity.", "Offer conservative first limit."],
      };
    }
    return {
      recommendation_code: "balanced_manual_review",
      title: "Balanced manual review",
      rationale: ["Risk is not low enough for automatic approval in the demo."],
      next_steps: ["Review income, debt load, and purpose.", "Record a human decision."],
    };
  }

  function createDecision(applicationId, actorEmail, payload) {
    const decision = {
      id: demo.nextDecisionId++,
      application_id: applicationId,
      actor_email: actorEmail,
      decision: payload.decision,
      policy_name: payload.policy_name || "balanced_review",
      note: payload.note || "",
      created_at: nowIso(),
    };
    demo.decisions[applicationId] = demo.decisions[applicationId] || [];
    demo.decisions[applicationId].push(decision);
    return decision;
  }

  function currentUser(session) {
    const sessionRecord = session?.token ? demo.sessions[session.token] : null;
    const sessionEmail = typeof sessionRecord === "string" ? sessionRecord : sessionRecord?.email;
    const expiresAt = typeof sessionRecord === "object" ? sessionRecord.session_expires_at : null;
    if (expiresAt && Date.parse(expiresAt) <= Date.now()) {
      delete demo.sessions[session.token];
      throw new Error("Demo session expired. Sign in again.");
    }
    const user = sessionEmail ? demo.users[sessionEmail] : null;
    if (!user || user.email !== session?.email || user.role !== session?.role) {
      throw new Error("Demo session expired. Sign in again.");
    }
    if (user.disabled_at) {
      delete demo.sessions[session.token];
      throw new Error("Account disabled");
    }
    return {
      email: user.email,
      role: user.role,
      organization_id: user.organization_id || null,
      created_at: user.created_at,
      disabled_at: user.disabled_at || null,
      disabled_by: user.disabled_by || null,
      mfa_attested_at: user.mfa_attested_at || null,
      mfa_attested_by: user.mfa_attested_by || null,
      mfa_method: user.mfa_method || null,
      session_expires_at: expiresAt,
      session_ttl_seconds: DEMO_SESSION_TTL_SECONDS,
    };
  }

  function requireMfi(session) {
    const user = currentUser(session);
    if (!["mfi_analyst", "admin"].includes(user.role)) throw new Error("MFI access required");
    return user;
  }

  function requireAdmin(session) {
    const user = currentUser(session);
    if (user.role !== "admin") throw new Error("Admin access required");
    return user;
  }

  function findApplication(applicationId) {
    const app = demo.applications.find((item) => item.id === applicationId);
    if (!app) throw new Error("Application not found");
    return app;
  }

  function mfiApplications(user) {
    if (user.role === "admin") return demo.applications;
    if (!user.organization_id) throw new Error("MFI analyst is not assigned to an organization");
    return demo.applications.filter((app) => app.organization_id === user.organization_id);
  }

  function mfiApplication(applicationId, user) {
    const app = findApplication(applicationId);
    if (user.role !== "admin" && app.organization_id !== user.organization_id) {
      throw new Error("Not allowed");
    }
    return app;
  }

  function visibleApplication(applicationId, session) {
    const user = currentUser(session);
    const app = findApplication(applicationId);
    const canReview = user.role === "admin" || (
      user.role === "mfi_analyst" && app.organization_id === user.organization_id
    );
    if (app.borrower_email !== user.email && !canReview) {
      throw new Error("Not allowed");
    }
    return app;
  }

  function borrowerApplication(application) {
    return {
      id: application.id,
      status: application.status,
      requested_amount: application.requested_amount,
      purpose: application.purpose,
      district: application.district,
      settlement_type: application.settlement_type,
      organization_id: application.organization_id,
      created_at: application.created_at,
      scored_at: application.scored_at,
      status_message: borrowerStatusMessages[application.status],
      terminal: terminalApplicationStatuses.has(application.status),
    };
  }

  function borrowerTimelineEvent(event) {
    return {
      ...event,
      actor_email: null,
      details: event.details?.status ? { status: event.details.status } : {},
    };
  }

  function lifecycleSummary(application) {
    const status = application.status;
    const terminal = terminalApplicationStatuses.has(status);
    const allowedDecisions = status === "scored"
      ? ["review", "approve", "decline"]
      : status === "under_review"
        ? ["approve", "decline"]
        : [];
    const notes = {
      submitted: "Application is ready for its first governed score.",
      scored: "Score is available; complete human review before a final decision.",
      under_review: "Manual review is open; record approve or decline after checks.",
      approved: "Approval is terminal in the prototype and cannot be silently reversed.",
      declined: "Decline is terminal in the prototype and cannot be silently reversed.",
    };
    return {
      status,
      terminal,
      scoring_action: terminal ? null : application.score_result ? "rescore" : "score",
      allowed_decisions: allowedDecisions,
      status_note: notes[status],
    };
  }

  function affordabilitySnapshot(application) {
    const signals = application.behavioral_signals || {};
    const optionalNumber = (field) => {
      if (signals[field] === null || signals[field] === undefined || signals[field] === "") return null;
      const value = Number(signals[field]);
      return Number.isFinite(value) && value >= 0 ? value : null;
    };
    const annualIncome = optionalNumber("annual_income");
    const outstandingDebt = optionalNumber("total_outstanding_debt");
    const openLoans = optionalNumber("num_open_loans");
    const values = {
      annual_income: annualIncome,
      total_outstanding_debt: outstandingDebt,
      num_open_loans: openLoans,
    };
    const missingFields = Object.entries(values)
      .filter(([, value]) => value === null)
      .map(([field]) => field);
    const incomeDenominator = annualIncome > 0 ? annualIncome : null;
    return {
      annual_income: annualIncome,
      total_outstanding_debt: outstandingDebt,
      num_open_loans: openLoans === null ? null : Math.trunc(openLoans),
      debt_to_income_ratio: incomeDenominator && outstandingDebt !== null
        ? outstandingDebt / incomeDenominator
        : null,
      requested_amount_to_income_ratio: incomeDenominator
        ? Number(application.requested_amount) / incomeDenominator
        : null,
      completeness: (Object.keys(values).length - missingFields.length) / Object.keys(values).length,
      missing_fields: missingFields,
      note: "Screening indicators only. Income period, loan term, expenses, and verified cash flow are required before any real affordability conclusion.",
    };
  }

  function reviewPacket(application) {
    const score = application.score_result;
    const flags = governanceFlags(application);
    return {
      application_id: application.id,
      generated_at: nowIso(),
      application: {
        id: application.id,
        borrower_email: application.borrower_email,
        status: application.status,
        requested_amount: application.requested_amount,
        purpose: application.purpose,
        district: application.district,
        settlement_type: application.settlement_type,
        organization_id: application.organization_id,
        created_at: application.created_at,
        scored_at: application.scored_at,
      },
      model_summary: score
        ? {
            model_name: score.model_name,
            model_version: score.model_version,
            feature_schema_version: score.model_governance?.feature_schema_version || null,
            training_data_label: score.model_governance?.training_data_label || null,
            activated_at: score.model_governance?.activated_at || null,
            is_current_active: score.model_version === activeModelVersion()?.version,
            risk_band: score.risk_band,
            high_risk_probability: score.high_risk_probability,
            proxy_sensitivity_delta: score.proxy_sensitivity_delta,
            missing_feature_count: score.missing_feature_count,
          }
        : null,
      decision_support: score?.decision_support || null,
      analyst_decision: application.decision_result,
      decision_history: demo.decisions[application.id] || [],
      lifecycle: lifecycleSummary(application),
      affordability: affordabilitySnapshot(application),
      timeline_events: demo.timelines[application.id] || [],
      scenario_scores: score?.scenario_scores || [],
      top_risk_factors: score?.explanation?.top_positive_factors || [],
      top_protective_factors: score?.explanation?.top_protective_factors || [],
      governance_flags: flags,
      checklist: reviewChecklist(application, flags),
      audit_note: "Static demo packet for portfolio review only. It is not a real lending record.",
    };
  }

  function governanceFlags(application) {
    const score = application.score_result;
    if (!score) return ["score_not_available"];
    const flags = [];
    if (!application.decision_result) flags.push("human_decision_not_recorded");
    if (score.risk_band === "high") flags.push("high_risk_application");
    if ((score.proxy_sensitivity_delta || 0) >= 0.2) flags.push("proxy_sensitive_score");
    if (score.model_version !== activeModelVersion()?.version) flags.push("stale_model_version");
    if (score.decision_support?.recommendation_code === "manual_review_proxy_sensitive") {
      flags.push("manual_review_proxy_sensitive");
    }
    return flags;
  }

  function reviewChecklist(application, flags) {
    const score = application.score_result;
    const decision = application.decision_result;
    const rows = [
      {
        code: "verify_identity",
        title: "Verify borrower identity and application ownership",
        status: "suggested",
        evidence: application.borrower_email,
      },
      {
        code: "verify_affordability",
        title: "Review income stability and repayment affordability",
        status: score ? "required" : "suggested",
        evidence: application.purpose || null,
      },
    ];
    if (flags.includes("proxy_sensitive_score")) {
      rows.push({
        code: "review_proxy_context",
        title: "Review late-payment context before declining",
        status: "required",
        evidence: "proxy_sensitivity_delta >= 0.20",
      });
    }
    if (flags.includes("stale_model_version")) {
      rows.push({
        code: "rescore_current_model",
        title: "Re-score with the currently active model before decision",
        status: "required",
        evidence: `scored_with=${score?.model_version || "unknown"}`,
      });
    }
    if (flags.includes("high_risk_application")) {
      rows.push({
        code: "senior_review",
        title: "Escalate high-risk cases before approval",
        status: "required",
        evidence: "risk_band=high",
      });
    }
    rows.push({
      code: "record_human_decision",
      title: "Record analyst decision and review note",
      status: decision ? "complete" : "required",
      evidence: decision?.note || null,
    });
    return rows;
  }

  function analyticsSegments(applications = demo.applications) {
    const scored = applications.filter((app) => app.score_result);
    const specs = [
      ["gender", (app) => app.behavioral_signals.gender || "unknown"],
      ["employment_status", (app) => app.behavioral_signals.employment_status || "unknown"],
      ["district", (app) => app.district || "unknown"],
    ];
    return specs.flatMap(([feature, getter]) => groupedRows(scored, getter).map((row) => ({
      segment_feature: feature,
      segment_value: row.key,
      n: row.items.length,
      avg_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      high_risk_share: share(row.items, (app) => app.score_result.risk_band === "high"),
    })));
  }

  function policyAnalytics(applications = demo.applications) {
    const scored = applications.filter((app) => app.score_result);
    const policies = thresholdPolicies().map((policy) => policyRow(
      scored,
      policy.name,
      policy.description,
      policy.approve_threshold,
      policy.decline_threshold,
    ));

    const balanced = policies[0];
    const segments = groupedRows(scored, (app) => app.district || "unknown")
      .slice(0, 5)
      .map((row) => segmentPolicyRow(row.items, balanced.policy, "district", row.key, balanced.approve_threshold, balanced.decline_threshold));

    return {
      scored_application_count: scored.length,
      policies,
      segments,
      note: "Static demo policy lab uses synthetic probabilities and is not a lending rule.",
    };
  }

  function policyRow(apps, policy, description, approveThreshold, declineThreshold) {
    const actions = apps.map((app) => policyAction(app.score_result.high_risk_probability, approveThreshold, declineThreshold));
    const approveCount = actions.filter((action) => action === "approve").length;
    const reviewCount = actions.filter((action) => action === "review").length;
    const declineCount = actions.filter((action) => action === "decline").length;
    const approvedProbabilities = apps
      .filter((_, index) => actions[index] === "approve")
      .map((app) => app.score_result.high_risk_probability);
    const reviewProbabilities = apps
      .filter((_, index) => actions[index] === "review")
      .map((app) => app.score_result.high_risk_probability);
    const declinedProbabilities = apps
      .filter((_, index) => actions[index] === "decline")
      .map((app) => app.score_result.high_risk_probability);
    const highRiskApproved = apps.filter(
      (app, index) => actions[index] === "approve" && app.score_result.risk_band === "high",
    ).length;
    return {
      policy,
      description,
      approve_threshold: approveThreshold,
      decline_threshold: declineThreshold,
      n: apps.length,
      auto_approve_count: approveCount,
      manual_review_count: reviewCount,
      auto_decline_count: declineCount,
      auto_approval_rate: rate(approveCount, apps.length),
      manual_review_rate: rate(reviewCount, apps.length),
      auto_decline_rate: rate(declineCount, apps.length),
      mean_high_risk_probability: average(apps.map((app) => app.score_result.high_risk_probability)),
      mean_approved_probability: average(approvedProbabilities),
      mean_review_probability: average(reviewProbabilities),
      mean_declined_probability: average(declinedProbabilities),
      predicted_high_risk_auto_approved_count: highRiskApproved,
      predicted_high_risk_auto_approval_rate: rate(highRiskApproved, apps.length),
    };
  }

  function segmentPolicyRow(apps, policy, segmentFeature, segmentValue, approveThreshold, declineThreshold) {
    const actions = apps.map((app) => policyAction(app.score_result.high_risk_probability, approveThreshold, declineThreshold));
    return {
      policy,
      segment_feature: segmentFeature,
      segment_value: segmentValue,
      n: apps.length,
      auto_approval_rate: rate(actions.filter((action) => action === "approve").length, apps.length),
      manual_review_rate: rate(actions.filter((action) => action === "review").length, apps.length),
      auto_decline_rate: rate(actions.filter((action) => action === "decline").length, apps.length),
      mean_high_risk_probability: average(apps.map((app) => app.score_result.high_risk_probability)),
      predicted_high_risk_share: share(apps, (app) => app.score_result.risk_band === "high"),
    };
  }

  function policyAction(probability, approveThreshold, declineThreshold) {
    if (probability <= approveThreshold) return "approve";
    if (probability >= declineThreshold) return "decline";
    return "review";
  }

  function thresholdPolicies() {
    return [
      {
        name: "balanced_review",
        description: "Middle policy with a substantial manual-review band.",
        approve_threshold: 0.35,
        decline_threshold: 0.70,
      },
      {
        name: "lender_protective",
        description: "Strict risk control; many applicants move to review or decline.",
        approve_threshold: 0.15,
        decline_threshold: 0.50,
      },
      {
        name: "inclusion_first",
        description: "Higher access; only very high-risk applicants are auto-declined.",
        approve_threshold: 0.50,
        decline_threshold: 0.85,
      },
      {
        name: "starter_loan_review",
        description: "Small-starter-loan posture with wide review before decline.",
        approve_threshold: 0.25,
        decline_threshold: 0.80,
      },
    ];
  }

  function seededRandom(seed) {
    let state = Number(seed) >>> 0;
    return () => {
      state += 0x6D2B79F5;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function normalRandom(random) {
    const left = Math.max(random(), 1e-12);
    const right = random();
    return Math.sqrt(-2 * Math.log(left)) * Math.cos(2 * Math.PI * right);
  }

  function simulationDistribution(values) {
    const sorted = [...values].sort((left, right) => left - right);
    const quantile = (probability) => {
      if (!sorted.length) return 0;
      const position = (sorted.length - 1) * probability;
      const lower = Math.floor(position);
      const upper = Math.ceil(position);
      if (lower === upper) return sorted[lower];
      return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
    };
    return {
      mean: average(values) || 0,
      p05: quantile(0.05),
      p50: quantile(0.50),
      p95: quantile(0.95),
    };
  }

  function simulationStandardError(values) {
    if (values.length < 2) return 0;
    const mean = average(values) || 0;
    const variance = values.reduce(
      (total, value) => total + (value - mean) ** 2,
      0,
    ) / (values.length - 1);
    return Math.sqrt(variance / values.length);
  }

  async function portfolioFingerprint(scored) {
    const records = scored
      .map((app) => ({
        application_id: String(app.id || "unknown"),
        high_risk_probability: clamp(
          Number(app.score_result.high_risk_probability),
          0.000001,
          0.999999,
        ),
        model_version: app.score_result.model_version || "unknown",
        requested_amount: Number(app.requested_amount),
        scored_at: app.scored_at || null,
      }))
      .sort((left, right) => left.application_id.localeCompare(right.application_id));
    const encoded = new TextEncoder().encode(JSON.stringify(records));
    const digest = await globalThis.crypto.subtle.digest("SHA-256", encoded);
    return [...new Uint8Array(digest)]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
  }

  async function simulatePortfolio(applications, payload) {
    const scored = applications.filter(
      (app) => app.score_result?.high_risk_probability !== null
        && app.score_result?.high_risk_probability !== undefined
        && Number(app.requested_amount) > 0,
    );
    if (!scored.length) throw new Error("Monte Carlo simulation requires at least one scored application");

    const iterations = Number(payload.iterations ?? 5000);
    const seed = Number(payload.seed ?? 20260619);
    const reviewApprovalRate = Number(payload.review_approval_rate ?? 0.5);
    const interestMarginRate = Number(payload.interest_margin_rate ?? 0.22);
    const lossGivenDefault = Number(payload.loss_given_default ?? 0.65);
    const operatingCost = Number(payload.operating_cost_per_approved ?? 0);
    const macroVolatility = Number(payload.macro_volatility ?? 0.25);
    const calibrationVolatility = Number(payload.calibration_volatility ?? 0.15);
    const scenarioShifts = { baseline: 0, adverse: 0.45, severe: 0.9 };
    const scenarios = [...new Set(payload.scenarios || ["baseline", "adverse", "severe"])];
    const unknownScenarios = scenarios.filter((scenario) => !Object.hasOwn(scenarioShifts, scenario));
    const policy = thresholdPolicies().find((item) => item.name === (payload.policy || "balanced_review"));
    if (!policy) throw new Error("Unknown threshold policy");
    if (iterations < 100 || iterations > 20000) throw new Error("Iterations must be between 100 and 20000");
    if (unknownScenarios.length) throw new Error(`Unknown stress scenarios: ${unknownScenarios.join(", ")}`);
    if (!scenarios.length) throw new Error("At least one stress scenario is required");
    [reviewApprovalRate, interestMarginRate, lossGivenDefault].forEach((value) => {
      if (value < 0 || value > 1) throw new Error("Simulation rates must be between 0 and 1");
    });
    if (operatingCost < 0 || macroVolatility < 0 || calibrationVolatility < 0) {
      throw new Error("Simulation cost and volatility assumptions cannot be negative");
    }
    const borrowerIterations = iterations * scored.length;
    if (borrowerIterations > 20000000) {
      throw new Error("Simulation workload is too large; reduce iterations or portfolio size below 20,000,000 borrower-iterations");
    }

    const random = seededRandom(seed);
    const paths = Object.fromEntries(scenarios.map((scenario) => [scenario, {
      approved_count: [],
      default_count: [],
      default_rate: [],
      approved_exposure: [],
      portfolio_result: [],
      result_per_approved: [],
      mean_stressed_probability: [],
    }]));
    const actions = scored.map((app) => policyAction(
      app.score_result.high_risk_probability,
      policy.approve_threshold,
      policy.decline_threshold,
    ));

    for (let iteration = 0; iteration < iterations; iteration += 1) {
      const macroShock = normalRandom(random);
      const calibrationShocks = scored.map(() => normalRandom(random));
      const reviewDraws = scored.map(() => random());
      const defaultDraws = scored.map(() => random());
      const entered = actions.map(
        (action, index) => action === "approve" || (action === "review" && reviewDraws[index] < reviewApprovalRate),
      );
      const approvedCount = entered.filter(Boolean).length;
      const approvedExposure = scored.reduce(
        (total, app, index) => total + (entered[index] ? Number(app.requested_amount) : 0),
        0,
      );

      scenarios.forEach((scenario) => {
        let defaultCount = 0;
        let portfolioResult = 0;
        let stressedProbabilityTotal = 0;
        scored.forEach((app, index) => {
          const baseProbability = clamp(Number(app.score_result.high_risk_probability), 0.000001, 0.999999);
          const baseLogit = Math.log(baseProbability / (1 - baseProbability));
          const stressedLogit = baseLogit
            + scenarioShifts[scenario]
            + macroVolatility * macroShock
            + calibrationVolatility * calibrationShocks[index];
          const stressedProbability = 1 / (1 + Math.exp(-clamp(stressedLogit, -30, 30)));
          stressedProbabilityTotal += stressedProbability;
          if (!entered[index]) return;
          const amount = Number(app.requested_amount);
          const defaulted = defaultDraws[index] < stressedProbability;
          if (defaulted) {
            defaultCount += 1;
            portfolioResult -= amount * lossGivenDefault + operatingCost;
          } else {
            portfolioResult += amount * interestMarginRate - operatingCost;
          }
        });
        const current = paths[scenario];
        current.approved_count.push(approvedCount);
        current.default_count.push(defaultCount);
        current.default_rate.push(approvedCount ? defaultCount / approvedCount : 0);
        current.approved_exposure.push(approvedExposure);
        current.portfolio_result.push(portfolioResult);
        current.result_per_approved.push(approvedCount ? portfolioResult / approvedCount : 0);
        current.mean_stressed_probability.push(stressedProbabilityTotal / scored.length);
      });
    }

    const modelVersions = [...new Set(scored.map((app) => app.score_result.model_version || "unknown"))].sort();
    const warnings = [];
    if (applications.length > scored.length) {
      warnings.push(`${applications.length - scored.length} applications were excluded because they lacked a usable score.`);
    }
    if (modelVersions.length > 1) {
      warnings.push("Portfolio contains scores from multiple model versions; compare or re-score before policy use.");
    }
    const activeVersion = activeModelVersion()?.version;
    const staleVersions = modelVersions.filter((version) => activeVersion && version !== activeVersion);
    if (staleVersions.length) {
      warnings.push(`Portfolio includes scores that are not from the active model version ${activeVersion}: ${staleVersions.join(", ")}.`);
    }
    if (operatingCost === 0) {
      warnings.push("Operating cost is zero; set an evidence-based cost before interpreting financial results.");
    }
    const fingerprint = await portfolioFingerprint(scored);

    return {
      simulation_id: `static-simulation-${Date.now()}-${demo.simulations.length + 1}`,
      generated_at: nowIso(),
      application_count: applications.length,
      scored_application_count: scored.length,
      unscored_application_count: applications.length - scored.length,
      model_versions: modelVersions,
      portfolio_fingerprint: fingerprint,
      policy: {
        ...policy,
        auto_approve_count: actions.filter((action) => action === "approve").length,
        manual_review_count: actions.filter((action) => action === "review").length,
        auto_decline_count: actions.filter((action) => action === "decline").length,
      },
      assumptions: {
        iterations,
        seed,
        review_approval_rate: reviewApprovalRate,
        interest_margin_rate: interestMarginRate,
        loss_given_default: lossGivenDefault,
        operating_cost_per_approved: operatingCost,
        macro_volatility: macroVolatility,
        calibration_volatility: calibrationVolatility,
        scenario_log_odds_shifts: Object.fromEntries(scenarios.map((scenario) => [scenario, scenarioShifts[scenario]])),
        borrower_iterations: borrowerIterations,
      },
      scenarios: scenarios.map((scenario) => {
        const current = paths[scenario];
        return {
          scenario,
          log_odds_shift: scenarioShifts[scenario],
          approved_count: simulationDistribution(current.approved_count),
          default_count: simulationDistribution(current.default_count),
          default_rate: simulationDistribution(current.default_rate),
          approved_exposure: simulationDistribution(current.approved_exposure),
          portfolio_result: simulationDistribution(current.portfolio_result),
          result_per_approved: simulationDistribution(current.result_per_approved),
          mean_stressed_probability: average(current.mean_stressed_probability) || 0,
          probability_of_loss: share(current.portfolio_result, (value) => value < 0),
          downside_p05: simulationDistribution(current.portfolio_result).p05,
          diagnostics: {
            portfolio_result_mean_standard_error: simulationStandardError(current.portfolio_result),
            default_count_mean_standard_error: simulationStandardError(current.default_count),
            loss_probability_standard_error: Math.sqrt(
              share(current.portfolio_result, (value) => value < 0)
              * (1 - share(current.portfolio_result, (value) => value < 0))
              / iterations,
            ),
          },
        };
      }),
      warnings,
      note: "Scenario-planning output only. Synthetic probabilities and assumptions are not forecasts or automatic lending decisions.",
    };
  }

  function simulationSummary(run) {
    return {
      simulation_id: run.simulation_id,
      generated_at: run.generated_at,
      organization_id: run.organization_id,
      actor_email: run.actor_email,
      portfolio_fingerprint: run.portfolio_fingerprint,
      policy: run.policy.name,
      iterations: run.assumptions.iterations,
      seed: run.assumptions.seed,
      scenarios: run.scenarios.map((row) => row.scenario),
      scored_application_count: run.scored_application_count,
      model_versions: run.model_versions,
      warning_count: run.warnings.length,
      scenario_summary: run.scenarios.map((row) => ({
        scenario: row.scenario,
        probability_of_loss: row.probability_of_loss,
        portfolio_result_p50: row.portfolio_result.p50,
      })),
    };
  }

  function decisionAnalytics(applications = demo.applications) {
    const apps = applications.filter((app) => app.score_result);
    const decided = apps.filter((app) => app.decision_result);
    return {
      application_count: applications.length,
      decided_application_count: decided.length,
      decision_rows: decisionRows(decided, () => "all").map((row) => ({
        decision: row.decision,
        count: row.count,
        rate: rate(row.count, decided.length),
      })),
      policy_rows: decisionRows(decided, (app) => app.decision_result.policy_name || "unknown").map((row) => ({
        policy_name: row.key,
        decision: row.decision,
        count: row.count,
        rate: rate(row.count, row.groupSize),
      })),
      risk_rows: decisionRows(decided, (app) => app.score_result.risk_band).map((row) => ({
        risk_band: row.key,
        decision: row.decision,
        count: row.count,
        rate_within_risk_band: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      })),
      district_rows: decisionRows(decided, (app) => app.district || "unknown").map((row) => ({
        district: row.key,
        decision: row.decision,
        count: row.count,
        rate_within_district: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      })),
      recommendation_rows: decisionRows(decided, (app) => app.score_result.decision_support?.recommendation_code || "unknown").map((row) => ({
        recommendation_code: row.key,
        recommendation_title: row.items[0]?.score_result.decision_support?.title || row.key,
        decision: row.decision,
        count: row.count,
        rate_within_recommendation: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      })),
      proxy_rows: decisionRows(decided, (app) => proxyBucket(app.score_result.proxy_sensitivity_delta)).map((row) => ({
        proxy_sensitivity_bucket: row.key,
        decision: row.decision,
        count: row.count,
        rate_within_bucket: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
        mean_proxy_sensitivity_delta: average(row.items.map((app) => app.score_result.proxy_sensitivity_delta)),
      })),
      note: "Static demo decision audit uses synthetic analyst decisions.",
    };
  }

  function decisionRows(apps, groupGetter) {
    return groupedRows(apps, groupGetter).flatMap((group) =>
      ["approve", "review", "decline"].map((decision) => {
        const items = group.items.filter((app) => app.decision_result?.decision === decision);
        return {
          key: group.key,
          decision,
          count: items.length,
          items,
          groupSize: group.items.length,
        };
      }).filter((row) => row.count > 0),
    );
  }

  function proxyBucket(value) {
    if ((value || 0) >= 0.2) return "high_proxy_sensitivity";
    if ((value || 0) >= 0.08) return "medium_proxy_sensitivity";
    return "low_proxy_sensitivity";
  }

  function groupedRows(items, getter) {
    const groups = {};
    items.forEach((item) => {
      const key = getter(item) || "unknown";
      groups[key] = groups[key] || [];
      groups[key].push(item);
    });
    return Object.entries(groups).map(([key, groupItems]) => ({ key, items: groupItems }));
  }

  function average(values) {
    const valid = values.filter((value) => value !== null && value !== undefined);
    if (!valid.length) return null;
    return valid.reduce((total, value) => total + Number(value), 0) / valid.length;
  }

  function share(items, predicate) {
    return items.length ? items.filter(predicate).length / items.length : 0;
  }

  function rate(count, total) {
    return total ? count / total : 0;
  }

  function portfolioCsv(applications = demo.applications) {
    const columns = [
      "application_id",
      "organization_id",
      "borrower_email",
      "status",
      "requested_amount",
      "district",
      "risk_band",
      "high_risk_probability",
      "proxy_sensitivity_delta",
      "decision",
      "policy_name",
    ];
    const rows = applications.map((app) => {
      const score = app.score_result || {};
      const decision = app.decision_result || {};
      return [
        app.id,
        app.organization_id,
        app.borrower_email,
        app.status,
        app.requested_amount,
        app.district || "",
        score.risk_band || "",
        score.high_risk_probability || "",
        score.proxy_sensitivity_delta || "",
        decision.decision || "",
        decision.policy_name || "",
      ];
    });
    return [columns, ...rows]
      .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
      .join("\n");
  }

  async function request(path, options = {}, session = {}) {
    const method = (options.method || "GET").toUpperCase();
    const body = parseBody(options);
    const cleanPath = path.split("?")[0];

    if (cleanPath === "/auth/login" && method === "POST") {
      const email = String(body.email || "").trim().toLowerCase();
      const user = demo.users[email];
      if (!user || user.password !== body.password) throw new Error("Invalid demo credentials");
      if (user.disabled_at) throw new Error("Account disabled");
      if (["admin", "mfi_analyst"].includes(user.role)) {
        if (!user.mfa_attested_at) {
          recordStaffMfaChallengeFailed({
            actorEmail: email,
            entityType: "user",
            entityId: email,
            reason: "missing_attestation",
            source: "login",
            mfaCode: body.mfa_code,
            method: user.mfa_method || "prototype_mfa_code",
            details: { role: user.role, organization_id: user.organization_id || null },
          });
          throw new Error("MFA attestation required before staff login");
        }
        if (!String(body.mfa_code || "").trim()) {
          recordStaffMfaChallengeFailed({
            actorEmail: email,
            entityType: "user",
            entityId: email,
            reason: "missing_code",
            source: "login",
            mfaCode: body.mfa_code,
            method: user.mfa_method || "prototype_mfa_code",
            details: { role: user.role, organization_id: user.organization_id || null },
          });
          throw new Error("MFA code required");
        }
        if (String(body.mfa_code).trim() !== DEMO_MFA_CODE) {
          recordStaffMfaChallengeFailed({
            actorEmail: email,
            entityType: "user",
            entityId: email,
            reason: "invalid_code",
            source: "login",
            mfaCode: body.mfa_code,
            method: user.mfa_method || "prototype_mfa_code",
            details: { role: user.role, organization_id: user.organization_id || null },
          });
          throw new Error("Invalid MFA code");
        }
      }
      const sessionRecord = createDemoSession(email);
      if (["admin", "mfi_analyst"].includes(user.role)) {
        addAudit("staff_mfa_login_verified", "user", email, email, {
          method: user.mfa_method || "prototype_mfa_code",
          prototype: true,
        });
      }
      return {
        access_token: sessionRecord.token,
        token_type: "bearer",
        role: user.role,
        organization_id: user.organization_id || null,
        session_expires_at: sessionRecord.session_expires_at,
        session_ttl_seconds: sessionRecord.session_ttl_seconds,
      };
    }

    if (cleanPath === "/auth/register" && method === "POST") {
      const email = String(body.email || "").trim().toLowerCase();
      if (body.role && body.role !== "borrower") {
        throw new Error("Public registration is limited to borrower accounts");
      }
      const passwordViolations = passwordPolicyViolations(body.password);
      if (passwordViolations.length) {
        throw new Error(`Password does not meet the registration policy: ${passwordViolations.join(", ")}`);
      }
      if (demo.users[email]) throw new Error("User already exists in static demo");
      demo.users[email] = {
        email,
        role: "borrower",
        organization_id: null,
        password: body.password || "",
        created_at: nowIso(),
        disabled_at: null,
        disabled_by: null,
        mfa_attested_at: null,
        mfa_attested_by: null,
        mfa_method: null,
      };
      const sessionRecord = createDemoSession(email);
      return {
        access_token: sessionRecord.token,
        token_type: "bearer",
        role: demo.users[email].role,
        organization_id: null,
        session_expires_at: sessionRecord.session_expires_at,
        session_ttl_seconds: sessionRecord.session_ttl_seconds,
      };
    }

    if (cleanPath === "/auth/accept-staff-invite" && method === "POST") {
      const token = String(body.token || "").trim();
      const tokenId = demo.staffInviteSecrets[token] || token;
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      if (invite.accepted_at) throw new Error("Staff invite has already been accepted");
      if (invite.revoked_at) throw new Error("Staff invite has been revoked");
      if (Date.parse(invite.expires_at) <= Date.now()) throw new Error("Staff invite has expired");
      const passwordViolations = passwordPolicyViolations(body.password);
      if (passwordViolations.length) {
        throw new Error(`Password does not meet the registration policy: ${passwordViolations.join(", ")}`);
      }
      if (!String(body.mfa_code || "").trim()) {
        recordStaffMfaChallengeFailed({
          actorEmail: invite.email,
          entityType: "staff_invite",
          entityId: tokenId,
          reason: "missing_code",
          source: "staff_invite_acceptance",
          mfaCode: body.mfa_code,
          details: {
            email: invite.email,
            role: invite.role,
            organization_id: invite.organization_id,
            token_preview: invite.token_preview,
          },
        });
        throw new Error("MFA code required");
      }
      if (String(body.mfa_code).trim() !== DEMO_MFA_CODE) {
        recordStaffMfaChallengeFailed({
          actorEmail: invite.email,
          entityType: "staff_invite",
          entityId: tokenId,
          reason: "invalid_code",
          source: "staff_invite_acceptance",
          mfaCode: body.mfa_code,
          details: {
            email: invite.email,
            role: invite.role,
            organization_id: invite.organization_id,
            token_preview: invite.token_preview,
          },
        });
        throw new Error("Invalid MFA code");
      }
      if (demo.users[invite.email]) throw new Error("User already exists in static demo");
      demo.users[invite.email] = {
        email: invite.email,
        role: invite.role,
        organization_id: invite.organization_id,
        password: body.password || "",
        created_at: nowIso(),
        disabled_at: null,
        disabled_by: null,
        mfa_attested_at: nowIso(),
        mfa_attested_by: invite.email,
        mfa_method: "prototype_mfa_code",
      };
      invite.accepted_at = nowIso();
      invite.accepted_by = invite.email;
      addAudit("staff_invite_accepted", "staff_invite", tokenId, invite.email, {
        email: invite.email,
        role: invite.role,
        organization_id: invite.organization_id,
        token_preview: invite.token_preview,
      });
      addAudit("staff_mfa_attested", "user", invite.email, invite.email, {
        method: "prototype_mfa_code",
        source: "staff_invite_acceptance",
        was_already_attested: false,
        limitation: "MFA Readiness v2 records staff attestation and the local prototype requires a second-factor code for staff sessions; it is not a production identity provider.",
      });
      const sessionRecord = createDemoSession(invite.email);
      addAudit("staff_mfa_login_verified", "user", invite.email, invite.email, {
        method: "prototype_mfa_code",
        prototype: true,
        source: "staff_invite_acceptance",
      });
      return {
        access_token: sessionRecord.token,
        token_type: "bearer",
        role: invite.role,
        organization_id: invite.organization_id,
        session_expires_at: sessionRecord.session_expires_at,
        session_ttl_seconds: sessionRecord.session_ttl_seconds,
      };
    }

    if (cleanPath === "/auth/logout" && method === "POST") {
      const user = currentUser(session);
      const revoked = Boolean(demo.sessions[session.token]);
      delete demo.sessions[session.token];
      addAudit("user_logged_out", "session", user.email, user.email, { role: user.role });
      return { revoked };
    }

    if (cleanPath === "/me" && method === "GET") {
      return clone(currentUser(session));
    }

    if (cleanPath === "/organizations" && method === "GET") {
      return clone(Object.values(demo.organizations));
    }

    if (cleanPath === "/applications" && method === "POST") {
      const user = currentUser(session);
      if (user.role !== "borrower") throw new Error("Borrower account required");
      validateApplicationPrivacy(body);
      validateApplicationContract(body);
      if (!demo.organizations[body.organization_id]) throw new Error("Select a valid MFI organization");
      const app = createApplicationRecord(body, user.email);
      demo.applications.unshift(app);
      addAudit("application_created", "application", app.id, user.email, {
        mode: "static_demo",
        consent_confirmed: true,
        consent_version: body.consent_version,
      });
      return clone(borrowerApplication(app));
    }

    if (cleanPath === "/applications" && method === "GET") {
      const user = currentUser(session);
      if (user.role !== "borrower") throw new Error("Borrower account required");
      return clone(
        demo.applications
          .filter((app) => app.borrower_email === user.email)
          .map(borrowerApplication),
      );
    }

    const appMatch = cleanPath.match(/^\/applications\/([^/]+)$/);
    if (appMatch && method === "GET") {
      const user = currentUser(session);
      if (user.role !== "borrower") throw new Error("Borrower account required");
      return clone(borrowerApplication(visibleApplication(decodeURIComponent(appMatch[1]), session)));
    }

    const timelineMatch = cleanPath.match(/^\/applications\/([^/]+)\/timeline$/);
    if (timelineMatch && method === "GET") {
      const user = currentUser(session);
      visibleApplication(decodeURIComponent(timelineMatch[1]), session);
      const events = demo.timelines[decodeURIComponent(timelineMatch[1])] || [];
      return clone(user.role === "borrower" ? events.map(borrowerTimelineEvent) : events);
    }

    if (cleanPath === "/mfi/applications" && method === "GET") {
      const user = requireMfi(session);
      return clone(mfiApplications(user));
    }

    if (cleanPath === "/mfi/model-status" && method === "GET") {
      requireMfi(session);
      const activeModel = activeModelVersion();
      return clone({
        scoring_allowed: Boolean(activeModel),
        active_model: activeModel,
        note: activeModel
          ? "Active model is registered for decision support only; human review remains required."
          : "Scoring is disabled until an administrator activates a model version.",
      });
    }

    const scoreMatch = cleanPath.match(/^\/mfi\/applications\/([^/]+)\/score$/);
    if (scoreMatch && method === "POST") {
      const user = requireMfi(session);
      const app = mfiApplication(decodeURIComponent(scoreMatch[1]), user);
      if (terminalApplicationStatuses.has(app.status)) {
        throw new Error(`Cannot score an application after it is ${app.status}`);
      }
      const previousStatus = app.status;
      const action = app.score_result ? "application_rescored" : "application_scored";
      app.score_result = buildScore(app);
      app.status = previousStatus === "submitted" ? "scored" : previousStatus;
      app.scored_at = nowIso();
      addTimeline(app.id, action, user.email, {
        model_version: app.score_result.model_version,
        risk_band: app.score_result.risk_band,
        previous_status: previousStatus,
        status: app.status,
      });
      addAudit(action, "application", app.id, user.email, { mode: "static_demo" });
      return clone(app);
    }

    const packetMatch = cleanPath.match(/^\/mfi\/applications\/([^/]+)\/review-packet$/);
    if (packetMatch && method === "GET") {
      const user = requireMfi(session);
      return clone(reviewPacket(mfiApplication(decodeURIComponent(packetMatch[1]), user)));
    }

    const decisionMatch = cleanPath.match(/^\/mfi\/applications\/([^/]+)\/decision$/);
    if (decisionMatch && method === "POST") {
      const user = requireMfi(session);
      const app = mfiApplication(decodeURIComponent(decisionMatch[1]), user);
      if (!app.score_result) throw new Error("Score the application before saving a decision");
      const allowedDecisions = app.status === "scored"
        ? new Set(["approve", "review", "decline"])
        : app.status === "under_review"
          ? new Set(["approve", "decline"])
          : new Set();
      if (!allowedDecisions.has(body.decision)) {
        throw new Error(`Cannot record ${body.decision} while application status is ${app.status}`);
      }
      const previousStatus = app.status;
      app.decision_result = createDecision(app.id, user.email, body);
      app.status = decisionWorkflowStatuses[body.decision];
      addTimeline(app.id, "application_decision_recorded", user.email, {
        decision: body.decision,
        policy_name: body.policy_name || "balanced_review",
        previous_status: previousStatus,
        status: app.status,
      });
      addAudit("application_decision_recorded", "application", app.id, user.email, { decision: body.decision });
      return clone(app);
    }

    if (cleanPath === "/mfi/analytics/segments" && method === "GET") {
      const user = requireMfi(session);
      return clone(analyticsSegments(mfiApplications(user)));
    }

    if (cleanPath === "/mfi/analytics/policies" && method === "GET") {
      const user = requireMfi(session);
      return clone(policyAnalytics(mfiApplications(user)));
    }

    if (cleanPath === "/mfi/simulations/portfolio" && method === "POST") {
      const user = requireMfi(session);
      const result = await simulatePortfolio(mfiApplications(user), body);
      result.organization_id = user.role === "admin" ? null : user.organization_id;
      result.actor_email = user.email;
      demo.simulations.unshift(clone(result));
      addAudit("portfolio_simulation_run", "portfolio_simulation", result.simulation_id, user.email, {
        organization_id: result.organization_id,
        policy: result.policy.name,
        iterations: result.assumptions.iterations,
        seed: result.assumptions.seed,
        scenarios: result.scenarios.map((row) => row.scenario),
        scored_application_count: result.scored_application_count,
        model_versions: result.model_versions,
      });
      return clone(result);
    }

    if (cleanPath === "/mfi/simulations" && method === "GET") {
      const user = requireMfi(session);
      const visible = user.role === "admin"
        ? demo.simulations
        : demo.simulations.filter((run) => run.organization_id === user.organization_id);
      return clone(visible.map(simulationSummary));
    }

    const simulationDetailMatch = cleanPath.match(/^\/mfi\/simulations\/([^/]+)$/);
    if (simulationDetailMatch && method === "GET") {
      const user = requireMfi(session);
      const simulationId = decodeURIComponent(simulationDetailMatch[1]);
      const run = demo.simulations.find((item) => item.simulation_id === simulationId);
      if (!run) throw new Error("Portfolio simulation not found");
      if (user.role !== "admin" && run.organization_id !== user.organization_id) {
        throw new Error("Not allowed");
      }
      return clone(run);
    }

    if (cleanPath === "/mfi/analytics/decisions" && method === "GET") {
      const user = requireMfi(session);
      return clone(decisionAnalytics(mfiApplications(user)));
    }

    if (cleanPath === "/admin/users" && method === "GET") {
      requireAdmin(session);
      return clone(
        Object.values(demo.users)
          .map(({
            email,
            role,
            organization_id,
            created_at,
            disabled_at,
            disabled_by,
            mfa_attested_at,
            mfa_attested_by,
            mfa_method,
          }) => ({
            email,
            role,
            organization_id: organization_id || null,
            created_at,
            disabled_at: disabled_at || null,
            disabled_by: disabled_by || null,
            mfa_attested_at: mfa_attested_at || null,
            mfa_attested_by: mfa_attested_by || null,
            mfa_method: mfa_method || null,
          }))
          .sort((left, right) => `${left.role}:${left.email}`.localeCompare(`${right.role}:${right.email}`)),
      );
    }

    if (cleanPath === "/admin/security/readiness" && method === "GET") {
      requireAdmin(session);
      return clone(securityReadiness());
    }

    if (cleanPath === "/admin/governance/pre-pilot-readiness" && method === "GET") {
      requireAdmin(session);
      return clone(prePilotReadiness(session));
    }

    if (cleanPath === "/admin/storage/postgresql-readiness" && method === "GET") {
      requireAdmin(session);
      return clone(postgresqlMigrationReadiness());
    }

    if (cleanPath === "/admin/security/identity-readiness" && method === "GET") {
      requireAdmin(session);
      return clone(identityReadiness(session));
    }

    if (cleanPath === "/admin/security/mfa-readiness" && method === "GET") {
      requireAdmin(session);
      return clone(mfaReadiness(demo.users));
    }

    const attestMfaMatch = cleanPath.match(/^\/admin\/users\/([^/]+)\/mfa\/attest$/);
    if (attestMfaMatch && method === "POST") {
      const user = requireAdmin(session);
      const email = decodeURIComponent(attestMfaMatch[1]).trim().toLowerCase();
      const target = demo.users[email];
      if (!target) throw new Error("User not found");
      if (!["admin", "mfi_analyst"].includes(target.role)) {
        throw new Error("Only active staff accounts require MFA attestation");
      }
      if (target.disabled_at) {
        throw new Error("Disabled staff accounts do not require MFA attestation");
      }
      const wasAlreadyAttested = Boolean(target.mfa_attested_at);
      if (!target.mfa_attested_at) {
        target.mfa_attested_at = nowIso();
        target.mfa_attested_by = user.email;
        target.mfa_method = body.method || "pilot_attestation";
      }
      if (!wasAlreadyAttested) {
        addAudit("staff_mfa_attested", "user", email, user.email, {
          role: target.role,
          organization_id: target.organization_id,
          method: target.mfa_method,
          limitation: "MFA Readiness v2 records staff attestation and the local prototype requires a second-factor code for staff sessions; it is not a production identity provider.",
        });
      }
      return clone({
        email: target.email,
        role: target.role,
        organization_id: target.organization_id || null,
        created_at: target.created_at,
        disabled_at: target.disabled_at || null,
        disabled_by: target.disabled_by || null,
        mfa_attested_at: target.mfa_attested_at || null,
        mfa_attested_by: target.mfa_attested_by || null,
        mfa_method: target.mfa_method || null,
        was_already_attested: wasAlreadyAttested,
      });
    }

    const disableStaffUserMatch = cleanPath.match(/^\/admin\/users\/([^/]+)\/disable$/);
    if (disableStaffUserMatch && method === "POST") {
      const user = requireAdmin(session);
      const email = decodeURIComponent(disableStaffUserMatch[1]).trim().toLowerCase();
      const target = demo.users[email];
      if (!target) throw new Error("User not found");
      if (target.role !== "mfi_analyst") {
        throw new Error("Only MFI analyst accounts can be disabled here");
      }
      const wasAlreadyDisabled = Boolean(target.disabled_at);
      if (!target.disabled_at) {
        target.disabled_at = nowIso();
        target.disabled_by = user.email;
      }
      let revokedSessionCount = 0;
      Object.entries(demo.sessions).forEach(([token, record]) => {
        const sessionEmail = typeof record === "string" ? record : record.email;
        if (sessionEmail === email) {
          delete demo.sessions[token];
          revokedSessionCount += 1;
        }
      });
      if (!wasAlreadyDisabled) {
        addAudit("staff_user_disabled", "user", email, user.email, {
          role: target.role,
          organization_id: target.organization_id,
          revoked_session_count: revokedSessionCount,
        });
      }
      return clone({
        email: target.email,
        role: target.role,
        organization_id: target.organization_id || null,
        created_at: target.created_at,
        disabled_at: target.disabled_at,
        disabled_by: target.disabled_by,
        mfa_attested_at: target.mfa_attested_at || null,
        mfa_attested_by: target.mfa_attested_by || null,
        mfa_method: target.mfa_method || null,
        revoked_session_count: revokedSessionCount,
        was_already_disabled: wasAlreadyDisabled,
      });
    }

    const reactivateStaffUserMatch = cleanPath.match(/^\/admin\/users\/([^/]+)\/reactivate$/);
    if (reactivateStaffUserMatch && method === "POST") {
      const user = requireAdmin(session);
      const email = decodeURIComponent(reactivateStaffUserMatch[1]).trim().toLowerCase();
      const target = demo.users[email];
      if (!target) throw new Error("User not found");
      if (target.role !== "mfi_analyst") {
        throw new Error("Only MFI analyst accounts can be reactivated here");
      }
      const wasAlreadyActive = !target.disabled_at;
      const previousDisabledAt = target.disabled_at || null;
      const previousDisabledBy = target.disabled_by || null;
      if (target.disabled_at) {
        target.disabled_at = null;
        target.disabled_by = null;
      }
      if (!wasAlreadyActive) {
        addAudit("staff_user_reactivated", "user", email, user.email, {
          role: target.role,
          organization_id: target.organization_id,
          previous_disabled_at: previousDisabledAt,
          previous_disabled_by: previousDisabledBy,
        });
      }
      return clone({
        email: target.email,
        role: target.role,
        organization_id: target.organization_id || null,
        created_at: target.created_at,
        disabled_at: target.disabled_at || null,
        disabled_by: target.disabled_by || null,
        mfa_attested_at: target.mfa_attested_at || null,
        mfa_attested_by: target.mfa_attested_by || null,
        mfa_method: target.mfa_method || null,
        was_already_active: wasAlreadyActive,
      });
    }

    if (cleanPath === "/admin/staff-sessions" && method === "GET") {
      requireAdmin(session);
      return clone(activeStaffSessions(session.token));
    }

    const revokeStaffSessionMatch = cleanPath.match(/^\/admin\/staff-sessions\/([^/]+)$/);
    if (revokeStaffSessionMatch && method === "DELETE") {
      const user = requireAdmin(session);
      const sessionId = decodeURIComponent(revokeStaffSessionMatch[1]).trim();
      const currentSessionId = sessionIdForToken(session.token);
      if (sessionId === currentSessionId) {
        throw new Error("Current admin session cannot be revoked from this endpoint; use logout.");
      }
      const target = Object.entries(demo.sessions)
        .map(([token, record]) => ({ token, row: publicStaffSession(token, record, session.token) }))
        .find((item) => item.row?.session_id === sessionId);
      if (!target?.row) throw new Error("Staff session not found");
      delete demo.sessions[target.token];
      addAudit("staff_session_revoked", "session", sessionId, user.email, {
        session_preview: target.row.session_preview,
        email: target.row.email,
        role: target.row.role,
        organization_id: target.row.organization_id,
        session_created_at: target.row.session_created_at,
        session_expires_at: target.row.session_expires_at,
      });
      return clone({
        revoked: true,
        session_id: target.row.session_id,
        email: target.row.email,
        role: target.row.role,
        organization_id: target.row.organization_id,
      });
    }

    if (cleanPath === "/admin/staff-invites" && method === "GET") {
      requireAdmin(session);
      return clone(
        Object.values(demo.staffInvites)
          .sort((left, right) => right.created_at.localeCompare(left.created_at))
          .map((invite) => publicStaffInvite(invite)),
      );
    }

    if (cleanPath === "/admin/staff-invites/health" && method === "GET") {
      requireAdmin(session);
      return clone(staffInviteHealth(Object.values(demo.staffInvites)));
    }

    if (cleanPath === "/admin/staff-invites/delivery-readiness" && method === "GET") {
      requireAdmin(session);
      return clone(inviteDeliveryReadiness());
    }

    if (cleanPath === "/admin/staff-invites/delivery-adapter-readiness" && method === "GET") {
      requireAdmin(session);
      return clone(inviteDeliveryAdapterReadiness());
    }

    if (cleanPath === "/admin/staff-invites/delivery-outbox" && method === "GET") {
      requireAdmin(session);
      return clone(inviteDeliveryOutbox());
    }

    if (cleanPath === "/admin/staff-invites/delivery-outbox/run" && method === "POST") {
      const user = requireAdmin(session);
      return clone(runInviteDeliveryOutbox(body, user.email));
    }

    if (cleanPath === "/webhooks/staff-invite-delivery" && method === "POST") {
      const { event, deliveryRecorded } = recordStaffInviteDeliveryWebhookEvent(body);
      return clone(publicStaffInviteDeliveryWebhookEvent(event, deliveryRecorded));
    }

    if (cleanPath === "/admin/staff-invites" && method === "POST") {
      const user = requireAdmin(session);
      const email = String(body.email || "").trim().toLowerCase();
      if (body.role && body.role !== "mfi_analyst") {
        throw new Error("Only MFI analyst invites can be created");
      }
      if (!demo.organizations[body.organization_id]) throw new Error("Select a valid MFI organization");
      if (demo.users[email]) throw new Error("User already exists in static demo");
      if (activePendingInviteForEmail(email)) throw new Error("Active staff invite already exists");
      const invite = createStaffInviteRecord({ ...body, email, role: "mfi_analyst" }, user.email);
      addAudit("staff_invite_created", "staff_invite", invite.token_id, user.email, {
        email: invite.email,
        role: invite.role,
        organization_id: invite.organization_id,
        expires_at: invite.expires_at,
        token_preview: invite.token_preview,
        source: "admin_create",
      });
      if (body.queue_delivery) {
        const storedInvite = demo.staffInvites[invite.token_id];
        const { attempt } = recordStaffInviteDeliveryAttempt(storedInvite, user.email, {
          provider: body.delivery_provider || "local_outbox",
          channel: body.delivery_channel || "email",
          recipient: body.delivery_recipient || email,
          note: body.delivery_note || null,
        });
        return clone({
          ...publicStaffInvite(storedInvite, invite.token),
          delivery_attempt: publicStaffInviteDeliveryAttempt(attempt),
        });
      }
      return clone(invite);
    }

    const deliverStaffInviteMatch = cleanPath.match(/^\/admin\/staff-invites\/([^/]+)\/delivery$/);
    if (deliverStaffInviteMatch && method === "POST") {
      const user = requireAdmin(session);
      const tokenId = decodeURIComponent(deliverStaffInviteMatch[1]);
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      if (invite.accepted_at) throw new Error("Accepted staff invite delivery is already complete");
      if (invite.revoked_at) throw new Error("Revoked staff invite cannot be delivered");
      if (Date.parse(invite.expires_at) <= Date.now()) throw new Error("Expired staff invite cannot be delivered");
      const { attempt, wasAlreadyDelivered } = recordStaffInviteDeliveryAttempt(invite, user.email, {
        provider: "manual_receipt",
        channel: body.channel || "manual_copy",
        recipient: body.recipient || invite.email,
        note: body.note || null,
      });
      return clone({
        ...publicStaffInvite({ ...invite, was_already_delivered: wasAlreadyDelivered }),
        delivery_attempt: publicStaffInviteDeliveryAttempt(attempt),
      });
    }

    const staffInviteDeliveryAttemptsMatch = cleanPath.match(/^\/admin\/staff-invites\/([^/]+)\/delivery-attempts$/);
    if (staffInviteDeliveryAttemptsMatch && method === "GET") {
      requireAdmin(session);
      const tokenId = decodeURIComponent(staffInviteDeliveryAttemptsMatch[1]);
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      return clone(staffInviteDeliveryAttempts(tokenId).map((attempt) => publicStaffInviteDeliveryAttempt(attempt)));
    }

    const staffInviteDeliveryEventsMatch = cleanPath.match(/^\/admin\/staff-invites\/([^/]+)\/delivery-events$/);
    if (staffInviteDeliveryEventsMatch && method === "GET") {
      requireAdmin(session);
      const tokenId = decodeURIComponent(staffInviteDeliveryEventsMatch[1]);
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      return clone(staffInviteDeliveryEvents(tokenId).map((event) => publicStaffInviteDeliveryWebhookEvent(event)));
    }

    const retryStaffInviteDeliveryMatch = cleanPath.match(/^\/admin\/staff-invites\/([^/]+)\/delivery-attempts\/retry$/);
    if (retryStaffInviteDeliveryMatch && method === "POST") {
      const user = requireAdmin(session);
      const tokenId = decodeURIComponent(retryStaffInviteDeliveryMatch[1]);
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      if (invite.accepted_at) throw new Error("Accepted staff invite delivery is already complete");
      if (invite.revoked_at) throw new Error("Revoked staff invite cannot be delivered");
      if (Date.parse(invite.expires_at) <= Date.now()) throw new Error("Expired staff invite cannot be delivered");
      const { attempt, wasAlreadyDelivered } = recordStaffInviteDeliveryAttempt(invite, user.email, {
        provider: body.provider || "local_outbox",
        channel: body.channel || "email",
        recipient: body.recipient || invite.email,
        note: body.note || null,
      });
      return clone({
        ...publicStaffInvite({ ...invite, was_already_delivered: wasAlreadyDelivered }),
        delivery_attempt: publicStaffInviteDeliveryAttempt(attempt),
      });
    }

    const rotateStaffInviteMatch = cleanPath.match(/^\/admin\/staff-invites\/([^/]+)\/rotate$/);
    if (rotateStaffInviteMatch && method === "POST") {
      const user = requireAdmin(session);
      const tokenId = decodeURIComponent(rotateStaffInviteMatch[1]);
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      if (invite.accepted_at) throw new Error("Accepted staff invite cannot be rotated");
      if (demo.users[invite.email]) throw new Error("User already exists in static demo");
      if (!demo.organizations[invite.organization_id]) throw new Error("Select a valid MFI organization");
      if (activePendingInviteForEmail(invite.email, tokenId)) throw new Error("Active staff invite already exists");
      const previousStatus = staffInviteLifecycleStatus(invite);
      if (!invite.revoked_at) {
        invite.revoked_at = nowIso();
        invite.revoked_by = user.email;
      }
      const rotated = createStaffInviteRecord(
        {
          email: invite.email,
          role: invite.role,
          organization_id: invite.organization_id,
          expires_in_hours: body.expires_in_hours || 48,
        },
        user.email,
      );
      addAudit("staff_invite_created", "staff_invite", rotated.token_id, user.email, {
        email: rotated.email,
        role: rotated.role,
        organization_id: rotated.organization_id,
        expires_at: rotated.expires_at,
        token_preview: rotated.token_preview,
        source: "staff_invite_rotation",
      });
      addAudit("staff_invite_rotated", "staff_invite", rotated.token_id, user.email, {
        email: rotated.email,
        role: rotated.role,
        organization_id: rotated.organization_id,
        previous_status: previousStatus,
        previous_token_preview: invite.token_preview,
        new_token_preview: rotated.token_preview,
        expires_at: rotated.expires_at,
      });
      if (body.queue_delivery) {
        const storedInvite = demo.staffInvites[rotated.token_id];
        const { attempt } = recordStaffInviteDeliveryAttempt(storedInvite, user.email, {
          provider: body.delivery_provider || "local_outbox",
          channel: body.delivery_channel || "email",
          recipient: body.delivery_recipient || storedInvite.email,
          note: body.delivery_note || null,
        });
        return clone({
          ...publicStaffInvite(storedInvite, rotated.token),
          delivery_attempt: publicStaffInviteDeliveryAttempt(attempt),
        });
      }
      return clone(rotated);
    }

    const revokeStaffInviteMatch = cleanPath.match(/^\/admin\/staff-invites\/([^/]+)$/);
    if (revokeStaffInviteMatch && method === "DELETE") {
      const user = requireAdmin(session);
      const tokenId = decodeURIComponent(revokeStaffInviteMatch[1]);
      const invite = demo.staffInvites[tokenId];
      if (!invite) throw new Error("Staff invite not found");
      if (invite.accepted_at) throw new Error("Accepted staff invite cannot be revoked");
      if (invite.revoked_at) return clone(invite);
      invite.revoked_at = nowIso();
      invite.revoked_by = user.email;
      addAudit("staff_invite_revoked", "staff_invite", tokenId, user.email, {
        email: invite.email,
        role: invite.role,
        organization_id: invite.organization_id,
        token_preview: invite.token_preview,
      });
      return clone(invite);
    }

    if (cleanPath === "/admin/model-versions" && method === "GET") {
      requireAdmin(session);
      return clone(
        Object.values(demo.modelVersions).sort((left, right) => {
          if (left.is_active !== right.is_active) return left.is_active ? -1 : 1;
          return right.created_at.localeCompare(left.created_at);
        }),
      );
    }

    if (cleanPath === "/admin/model-versions" && method === "POST") {
      const user = requireAdmin(session);
      const version = String(body.version || "").trim();
      if (!/^[A-Za-z0-9._-]{3,100}$/.test(version)) throw new Error("Invalid model version");
      if (demo.modelVersions[version]) throw new Error("Model version already exists");
      if (!Array.isArray(body.limitations) || !body.limitations.length) {
        throw new Error("Record at least one model limitation");
      }
      demo.modelVersions[version] = {
        version,
        model_name: body.model_name || "Logistic Regression",
        model_type: "logistic_regression",
        lifecycle_status: "candidate",
        is_active: false,
        feature_schema_version: body.feature_schema_version,
        training_data_label: body.training_data_label,
        random_state: Number(body.random_state ?? 42),
        metrics: body.metrics || {},
        limitations: body.limitations.map((item) => String(item).trim()).filter(Boolean),
        created_by: user.email,
        created_at: nowIso(),
        activated_at: null,
      };
      addAudit("model_version_registered", "model_version", version, user.email, {
        feature_schema_version: body.feature_schema_version,
        training_data_label: body.training_data_label,
      });
      return clone(demo.modelVersions[version]);
    }

    const activateModelMatch = cleanPath.match(/^\/admin\/model-versions\/([^/]+)\/activate$/);
    if (activateModelMatch && method === "POST") {
      const user = requireAdmin(session);
      const version = decodeURIComponent(activateModelMatch[1]);
      const target = demo.modelVersions[version];
      if (!target) throw new Error("Model version not found");
      const previous = activeModelVersion();
      Object.values(demo.modelVersions).forEach((model) => {
        if (model.is_active && model.version !== version) {
          model.is_active = false;
          model.lifecycle_status = "inactive";
        }
      });
      target.is_active = true;
      target.lifecycle_status = "active";
      target.activated_at = nowIso();
      addAudit("model_version_activated", "model_version", version, user.email, {
        previous_active_version: previous?.version || null,
        random_state: target.random_state,
      });
      return clone(target);
    }

    if (cleanPath === "/admin/users" && method === "POST") {
      const user = requireAdmin(session);
      const email = String(body.email || "").trim().toLowerCase();
      if (body.role !== "mfi_analyst") throw new Error("Only MFI analyst accounts can be provisioned");
      if (!demo.organizations[body.organization_id]) throw new Error("Select a valid MFI organization");
      const passwordViolations = passwordPolicyViolations(body.password);
      if (passwordViolations.length) {
        throw new Error(`Password does not meet the registration policy: ${passwordViolations.join(", ")}`);
      }
      if (demo.users[email]) throw new Error("User already exists in static demo");
      demo.users[email] = {
        email,
        role: "mfi_analyst",
        organization_id: body.organization_id,
        password: body.password,
        created_at: nowIso(),
        disabled_at: null,
        disabled_by: null,
        mfa_attested_at: null,
        mfa_attested_by: null,
        mfa_method: null,
      };
      addAudit("staff_user_created", "user", email, user.email, {
        role: "mfi_analyst",
        organization_id: body.organization_id,
      });
      return clone({
        email,
        role: "mfi_analyst",
        organization_id: body.organization_id,
        created_at: demo.users[email].created_at,
        disabled_at: null,
        disabled_by: null,
        mfa_attested_at: null,
        mfa_attested_by: null,
        mfa_method: null,
      });
    }

    if (cleanPath === "/admin/organizations" && method === "POST") {
      const user = requireAdmin(session);
      const organizationId = String(body.id || "").trim().toLowerCase();
      if (demo.organizations[organizationId]) throw new Error("Organization already exists");
      demo.organizations[organizationId] = {
        id: organizationId,
        name: body.name,
        region: body.region,
        created_at: nowIso(),
      };
      addAudit("organization_created", "mfi_organization", organizationId, user.email, {
        name: body.name,
        region: body.region,
      });
      return clone(demo.organizations[organizationId]);
    }

    if (cleanPath === "/admin/audit-events" && method === "GET") {
      requireAdmin(session);
      return clone(demo.auditEvents);
    }

    if (cleanPath === "/admin/applications" && method === "DELETE") {
      const user = requireAdmin(session);
      const deletedCount = demo.applications.length;
      demo.applications = [];
      demo.decisions = {};
      demo.timelines = {};
      addAudit("applications_cleared", "portfolio", "static-demo", user.email, { deleted_count: deletedCount });
      return { deleted_count: deletedCount };
    }

    throw new Error(`Static demo endpoint not implemented: ${method} ${cleanPath}`);
  }

  async function blob(path, session = {}) {
    if (path === "/mfi/applications/export.csv") {
      const user = requireMfi(session);
      return new Blob(
        [portfolioCsv(mfiApplications(user))],
        { type: "text/csv;charset=utf-8" },
      );
    }
    throw new Error(`Static demo file endpoint not implemented: ${path}`);
  }

  resetDemo();

  window.MicroScoreMockApi = {
    request,
    blob,
    resetDemo,
  };
})();
