const fs = require("fs");
const vm = require("vm");

global.window = {};
window.MicroScoreApplicationIntake = require("../apps/web/application-intake.js");
window.MicroScorePortfolioDashboard = require("../apps/web/portfolio-dashboard.js");
window.MicroScoreRiskDetail = require("../apps/web/risk-detail.js");
vm.runInThisContext(fs.readFileSync("apps/web/mock-api.js", "utf8"));

async function main() {
  const api = window.MicroScoreMockApi;
  if (!api) throw new Error("MicroScoreMockApi was not registered");

  const auth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "analyst@test.com",
      password: "password123",
      mfa_code: "246810",
    }),
  });
  if (!auth.session_expires_at || auth.session_ttl_seconds !== 8 * 60 * 60) {
    throw new Error("Expected static auth response to include session expiry metadata");
  }
  const session = {
    token: auth.access_token,
    role: auth.role,
    email: "analyst@test.com",
  };

  const applications = await api.request("/mfi/applications", {}, session);
  if (applications.length < 3) {
    throw new Error(`Expected seeded applications, got ${applications.length}`);
  }
  const portfolioDashboard = window.MicroScorePortfolioDashboard.summarizePortfolioDashboard(applications);
  if (
    portfolioDashboard.scoredCount < 3
    || !portfolioDashboard.settlementRows.some((row) => row.key === "industrial_city")
    || !portfolioDashboard.topDistrict
  ) {
    throw new Error("Expected Portfolio Dashboard v2 summary with district and settlement rows");
  }

  const scored = await api.request(
    `/mfi/applications/${applications[2].id}/score`,
    { method: "POST" },
    session,
  );
  if (!scored.score_result?.risk_band) {
    throw new Error("Expected score result with risk band");
  }

  const packet = await api.request(
    `/mfi/applications/${scored.id}/review-packet`,
    {},
    session,
  );
  if (!packet.checklist?.length) {
    throw new Error("Expected review packet checklist");
  }
  if (
    packet.lifecycle.status !== "scored"
    || packet.affordability.completeness !== 1
    || packet.decision_history.length !== 0
  ) {
    throw new Error("Expected Risk Detail v2 lifecycle and affordability contract");
  }

  const policies = await api.request("/mfi/analytics/policies", {}, session);
  if (policies.policies.length < 3) {
    throw new Error("Expected multiple policy scenarios");
  }

  const simulationRequest = {
    method: "POST",
    body: JSON.stringify({
      iterations: 500,
      seed: 20260619,
      policy: "balanced_review",
      scenarios: ["baseline", "adverse", "severe"],
      review_approval_rate: 0.5,
      interest_margin_rate: 0.22,
      loss_given_default: 0.65,
      operating_cost_per_approved: 50,
      macro_volatility: 0.25,
      calibration_volatility: 0.15,
    }),
  };
  const simulation = await api.request(
    "/mfi/simulations/portfolio",
    simulationRequest,
    session,
  );
  const repeatedSimulation = await api.request(
    "/mfi/simulations/portfolio",
    simulationRequest,
    session,
  );
  if (JSON.stringify(simulation.scenarios) !== JSON.stringify(repeatedSimulation.scenarios)) {
    throw new Error("Expected seeded Monte Carlo simulation to be reproducible");
  }
  if (
    simulation.portfolio_fingerprint.length !== 64
    || simulation.portfolio_fingerprint !== repeatedSimulation.portfolio_fingerprint
  ) {
    throw new Error("Expected stable SHA-256 portfolio fingerprint");
  }
  if (simulation.scenarios.some((row) => !row.diagnostics)) {
    throw new Error("Expected Monte Carlo standard-error diagnostics");
  }
  const simulationHistory = await api.request("/mfi/simulations", {}, session);
  if (simulationHistory.length !== 2) {
    throw new Error("Expected immutable simulation history entries");
  }
  const storedSimulation = await api.request(
    `/mfi/simulations/${simulation.simulation_id}`,
    {},
    session,
  );
  if (storedSimulation.portfolio_fingerprint !== simulation.portfolio_fingerprint) {
    throw new Error("Expected stored simulation detail to preserve fingerprint");
  }
  const simulatedScenarios = Object.fromEntries(
    simulation.scenarios.map((row) => [row.scenario, row]),
  );
  if (
    simulatedScenarios.baseline.default_count.mean > simulatedScenarios.adverse.default_count.mean
    || simulatedScenarios.adverse.default_count.mean > simulatedScenarios.severe.default_count.mean
  ) {
    throw new Error("Expected stress scenarios to increase simulated defaults");
  }
  if (!simulation.note.includes("Scenario-planning")) {
    throw new Error("Expected Monte Carlo interpretation boundary");
  }

  const csv = await api.blob("/mfi/applications/export.csv", session);
  if (!csv.size) {
    throw new Error("Expected non-empty portfolio CSV");
  }

  const borrowerAuth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "borrower@test.com",
      password: "password123",
    }),
  });
  const borrowerSession = {
    token: borrowerAuth.access_token,
    role: borrowerAuth.role,
    email: "borrower@test.com",
  };
  const borrowerHistory = await api.request("/applications", {}, borrowerSession);
  if (borrowerHistory.length !== 5 || borrowerHistory.some((row) => row.score_result)) {
    throw new Error("Expected borrower-safe application history without internal scores");
  }
  const lifecycleApplication = await api.request(
    "/applications",
    {
      method: "POST",
      body: JSON.stringify({
        requested_amount: 2100,
        purpose: "inventory",
        district: "Aksu",
        settlement_type: "industrial_city",
        organization_id: "pavlodar-demo-mfi",
        consent_confirmed: true,
        consent_version: "synthetic-demo-v1",
        behavioral_signals: {
          annual_income: 42000,
          total_outstanding_debt: 2500,
          late_payment_count: 0,
        },
      }),
    },
    borrowerSession,
  );
  const draftPacket = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/review-packet`,
    {},
    session,
  );
  const draftPlan = window.MicroScoreRiskDetail.buildReviewActionPlan(draftPacket);
  if (
    draftPlan.stage !== "score_first"
    || !draftPlan.score_enabled
    || draftPlan.decision_enabled
    || draftPlan.allowed_decisions.length
  ) {
    throw new Error("Expected Review Readiness action plan to require scoring first");
  }
  const lifecycleScored = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/score`,
    { method: "POST" },
    session,
  );
  const lifecycleReviewed = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: "review",
        policy_name: "balanced_review",
        note: "Verify seasonal income.",
      }),
    },
    session,
  );
  if (lifecycleScored.status !== "scored" || lifecycleReviewed.status !== "under_review") {
    throw new Error("Expected submitted to scored to under-review lifecycle");
  }
  const reviewActionPacket = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/review-packet`,
    {},
    session,
  );
  const reviewActionPlan = window.MicroScoreRiskDetail.buildReviewActionPlan(reviewActionPacket);
  if (
    reviewActionPlan.stage !== "finalize_decision"
    || reviewActionPlan.allowed_decisions.includes("review")
    || !reviewActionPlan.allowed_decisions.includes("approve")
    || !reviewActionPlan.decision_enabled
  ) {
    throw new Error("Expected Review Readiness action plan to expose final decision actions");
  }
  const lifecycleRescored = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/score`,
    { method: "POST" },
    session,
  );
  if (lifecycleRescored.status !== "under_review") {
    throw new Error("Expected rescore to preserve under-review status");
  }
  const lifecycleApproved = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: "approve",
        policy_name: "balanced_review",
        note: "Evidence verified.",
      }),
    },
    session,
  );
  if (lifecycleApproved.status !== "approved") {
    throw new Error("Expected reviewed application to reach approved terminal state");
  }
  const lifecyclePacket = await api.request(
    `/mfi/applications/${lifecycleApplication.id}/review-packet`,
    {},
    session,
  );
  const terminalPlan = window.MicroScoreRiskDetail.buildReviewActionPlan(lifecyclePacket);
  if (
    !lifecyclePacket.lifecycle.terminal
    || lifecyclePacket.decision_history.length !== 2
    || terminalPlan.stage !== "terminal_locked"
    || terminalPlan.score_enabled
    || terminalPlan.decision_enabled
  ) {
    throw new Error("Expected terminal risk detail with complete decision history");
  }
  let terminalMutationRejected = false;
  try {
    await api.request(
      `/mfi/applications/${lifecycleApplication.id}/score`,
      { method: "POST" },
      session,
    );
  } catch (error) {
    terminalMutationRejected = String(error.message).includes("after it is approved");
  }
  if (!terminalMutationRejected) throw new Error("Expected terminal lifecycle mutation to fail");
  const lifecycleTimeline = await api.request(
    `/applications/${lifecycleApplication.id}/timeline`,
    {},
    borrowerSession,
  );
  const borrowerTerminalDetail = await api.request(
    `/applications/${lifecycleApplication.id}`,
    {},
    borrowerSession,
  );
  if (
    lifecycleTimeline.some((event) => event.actor_email || event.details.risk_band)
    || lifecycleTimeline.at(-1)?.title !== "Application approved"
  ) {
    throw new Error("Expected borrower-safe lifecycle timeline");
  }
  if (
    borrowerTerminalDetail.status !== "approved"
    || !borrowerTerminalDetail.terminal
    || !String(borrowerTerminalDetail.status_message || "").includes("final status")
    || borrowerTerminalDetail.score_result
    || borrowerTerminalDetail.decision_result
    || borrowerTerminalDetail.behavioral_signals
    || borrowerTerminalDetail.actor_email
    || borrowerTerminalDetail.policy_name
  ) {
    throw new Error("Expected borrower terminal detail to remain status-only and borrower-safe");
  }

  let privilegedRegistrationRejected = false;
  try {
    await api.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: "self-admin@test.com",
        password: "StrongPassword1!",
        role: "admin",
      }),
    });
  } catch (error) {
    privilegedRegistrationRejected = String(error.message).includes("borrower accounts");
  }
  if (!privilegedRegistrationRejected) {
    throw new Error("Expected privileged public registration to be rejected");
  }

  let weakPasswordRejected = false;
  try {
    await api.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: "weak-password@test.com",
        password: "password123",
        role: "borrower",
      }),
    });
  } catch (error) {
    weakPasswordRejected = String(error.message).includes("registration policy");
  }
  if (!weakPasswordRejected) throw new Error("Expected weak password to be rejected");

  const registeredBorrower = await api.request("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email: "new-borrower@test.com",
      password: "StrongPassword1!",
      role: "borrower",
    }),
  });
  if (registeredBorrower.role !== "borrower") {
    throw new Error("Expected public registration to create a borrower account");
  }

  const adminAuth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "admin@test.com",
      password: "password123",
      mfa_code: "246810",
    }),
  });
  const adminSession = {
    token: adminAuth.access_token,
    role: adminAuth.role,
    email: "admin@test.com",
  };
  const mfaReadinessBefore = await api.request("/admin/security/mfa-readiness", {}, adminSession);
  if (
    mfaReadinessBefore.status !== "ready"
    || mfaReadinessBefore.missing_mfa_count !== 0
    || !String(mfaReadinessBefore.limitation).includes("requires a second-factor code")
  ) {
    throw new Error("Expected seeded staff MFA readiness to be ready with prototype enforcement");
  }
  const mfaAttested = await api.request(
    `/admin/users/${encodeURIComponent("admin@test.com")}/mfa/attest`,
    {
      method: "POST",
      body: JSON.stringify({ method: "pilot_attestation" }),
    },
    adminSession,
  );
  if (
    !mfaAttested.mfa_attested_at
    || mfaAttested.mfa_attested_by !== "admin@test.com"
    || mfaAttested.mfa_method !== "prototype_mfa_code"
    || !mfaAttested.was_already_attested
  ) {
    throw new Error("Expected seeded admin MFA attestation metadata");
  }
  const mfaReadinessAfter = await api.request("/admin/security/mfa-readiness", {}, adminSession);
  if (mfaReadinessAfter.mfa_attested_count < 1) {
    throw new Error("Expected MFA readiness to include attested staff count");
  }
  const securityReadinessAfterMfa = await api.request("/admin/security/readiness", {}, adminSession);
  if (
    securityReadinessAfterMfa.status !== "ready"
    || !securityReadinessAfterMfa.checks.some((check) => check.key === "mfa_enforcement" && check.status === "pass")
    || !securityReadinessAfterMfa.checks.some((check) => check.key === "invite_delivery" && check.status === "pass")
  ) {
    throw new Error("Expected security readiness to be ready with MFA enforcement and no pending invites");
  }
  const identityReadinessInitial = await api.request("/admin/security/identity-readiness", {}, adminSession);
  if (
    identityReadinessInitial.status !== "blocked"
    || identityReadinessInitial.auth_provider_mode !== "local_password_prototype"
    || identityReadinessInitial.storage_backend !== "sqlite_static_demo"
    || identityReadinessInitial.mfa_mode !== "prototype_shared_code_with_admin_attestation"
    || identityReadinessInitial.session_control_mode !== "local_bearer_sessions_with_admin_revoke"
    || identityReadinessInitial.tenant_isolation_mode !== "organization_id_scoped_mfi_access"
    || !identityReadinessInitial.components?.some((row) => row.key === "auth_provider" && row.status === "blocker")
    || !identityReadinessInitial.components?.some((row) => row.key === "mfa_posture" && row.status === "warning")
    || !String(identityReadinessInitial.limitation || "").includes("not a completed production security review")
  ) {
    throw new Error("Expected identity readiness evidence room to show local prototype limitations");
  }
  const inviteDeliveryReadinessInitial = await api.request("/admin/staff-invites/delivery-readiness", {}, adminSession);
  if (
    inviteDeliveryReadinessInitial.status !== "blocked"
    || inviteDeliveryReadinessInitial.configured_provider !== "local_outbox"
    || !inviteDeliveryReadinessInitial.invite_url_https
    || inviteDeliveryReadinessInitial.invite_url_local
    || !inviteDeliveryReadinessInitial.production_blockers?.some((row) => row.key === "delivery_provider_not_production_ready")
    || !inviteDeliveryReadinessInitial.providers?.some((row) => row.provider === "transactional_email" && row.requires_external_secret)
  ) {
    throw new Error("Expected invite delivery readiness to expose local provider contract blockers");
  }
  const usersBeforeProvisioning = await api.request("/admin/users", {}, adminSession);
  const staffUser = await api.request(
    "/admin/users",
    {
      method: "POST",
      body: JSON.stringify({
        email: "new-analyst@test.com",
        password: "StrongPassword1!",
        role: "mfi_analyst",
        organization_id: "pavlodar-demo-mfi",
      }),
    },
    adminSession,
  );
  const usersAfterProvisioning = await api.request("/admin/users", {}, adminSession);
  if (staffUser.role !== "mfi_analyst") throw new Error("Expected MFI analyst account");
  if (usersAfterProvisioning.length !== usersBeforeProvisioning.length + 1) {
    throw new Error("Expected provisioned analyst in the user list");
  }
  let missingMfaLoginRejected = false;
  try {
    await api.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: "new-analyst@test.com",
        password: "StrongPassword1!",
        mfa_code: "246810",
      }),
    });
  } catch (error) {
    missingMfaLoginRejected = String(error.message).includes("MFA attestation required");
  }
  if (!missingMfaLoginRejected) {
    throw new Error("Expected provisioned staff login to require MFA attestation first");
  }
  const mfaFailureReadiness = await api.request("/admin/security/readiness", {}, adminSession);
  if (!mfaFailureReadiness.checks.some((check) => check.key === "mfa_challenge_failures" && check.status === "warning")) {
    throw new Error("Expected failed staff MFA challenge to raise Security Readiness warning");
  }
  const analystMfaAttested = await api.request(
    `/admin/users/${encodeURIComponent("new-analyst@test.com")}/mfa/attest`,
    {
      method: "POST",
      body: JSON.stringify({ method: "pilot_attestation" }),
    },
    adminSession,
  );
  if (!analystMfaAttested.mfa_attested_at) {
    throw new Error("Expected provisioned analyst MFA attestation metadata");
  }
  let newAnalystAuth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "new-analyst@test.com",
      password: "StrongPassword1!",
      mfa_code: "246810",
    }),
  });
  let newAnalystSession = {
    token: newAnalystAuth.access_token,
    role: newAnalystAuth.role,
    email: "new-analyst@test.com",
  };
  const staffSessions = await api.request("/admin/staff-sessions", {}, adminSession);
  const currentAdminSession = staffSessions.find((item) => item.email === "admin@test.com" && item.is_current_session);
  const analystSession = staffSessions.find((item) => item.email === "new-analyst@test.com" && !item.is_current_session);
  if (!currentAdminSession || !analystSession || analystSession.token || !analystSession.session_expires_at) {
    throw new Error("Expected staff session inventory to expose safe active session metadata");
  }
  let selfRevokeRejected = false;
  try {
    await api.request(
      `/admin/staff-sessions/${encodeURIComponent(currentAdminSession.session_id)}`,
      { method: "DELETE" },
      adminSession,
    );
  } catch (error) {
    selfRevokeRejected = String(error.message).includes("Current admin session");
  }
  if (!selfRevokeRejected) throw new Error("Expected current admin session revoke guard");
  const revokedStaffSession = await api.request(
    `/admin/staff-sessions/${encodeURIComponent(analystSession.session_id)}`,
    { method: "DELETE" },
    adminSession,
  );
  if (!revokedStaffSession.revoked || revokedStaffSession.email !== "new-analyst@test.com") {
    throw new Error("Expected admin staff session revoke response");
  }
  let revokedStaffSessionRejected = false;
  try {
    await api.request("/me", {}, newAnalystSession);
  } catch (error) {
    revokedStaffSessionRejected = String(error.message).includes("session expired");
  }
  if (!revokedStaffSessionRejected) throw new Error("Expected revoked staff session token to fail");
  newAnalystAuth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "new-analyst@test.com",
      password: "StrongPassword1!",
      mfa_code: "246810",
    }),
  });
  newAnalystSession = {
    token: newAnalystAuth.access_token,
    role: newAnalystAuth.role,
    email: "new-analyst@test.com",
  };
  const disabledAnalyst = await api.request(
    `/admin/users/${encodeURIComponent("new-analyst@test.com")}/disable`,
    { method: "POST" },
    adminSession,
  );
  if (
    !disabledAnalyst.disabled_at
    || disabledAnalyst.disabled_by !== "admin@test.com"
    || disabledAnalyst.revoked_session_count !== 1
  ) {
    throw new Error("Expected disabled staff user with revoked session count");
  }
  let disabledTokenRejected = false;
  try {
    await api.request("/me", {}, newAnalystSession);
  } catch (error) {
    disabledTokenRejected = String(error.message).includes("session expired")
      || String(error.message).includes("disabled");
  }
  if (!disabledTokenRejected) {
    throw new Error("Expected disabled staff user's active session to be revoked");
  }
  let disabledLoginRejected = false;
  try {
    await api.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: "new-analyst@test.com",
        password: "StrongPassword1!",
        mfa_code: "246810",
      }),
    });
  } catch (error) {
    disabledLoginRejected = String(error.message).includes("Account disabled");
  }
  if (!disabledLoginRejected) throw new Error("Expected disabled staff login to fail");
  const repeatedDisabledAnalyst = await api.request(
    `/admin/users/${encodeURIComponent("new-analyst@test.com")}/disable`,
    { method: "POST" },
    adminSession,
  );
  if (!repeatedDisabledAnalyst.was_already_disabled) {
    throw new Error("Expected repeated staff disable to be idempotent");
  }
  const usersAfterDisable = await api.request("/admin/users", {}, adminSession);
  if (!usersAfterDisable.some((user) => user.email === "new-analyst@test.com" && user.disabled_at)) {
    throw new Error("Expected disabled analyst in the user list");
  }
  const reactivatedAnalyst = await api.request(
    `/admin/users/${encodeURIComponent("new-analyst@test.com")}/reactivate`,
    { method: "POST" },
    adminSession,
  );
  if (
    reactivatedAnalyst.disabled_at
    || reactivatedAnalyst.disabled_by
    || reactivatedAnalyst.was_already_active
  ) {
    throw new Error("Expected reactivated analyst without disabled metadata");
  }
  const reactivatedLogin = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "new-analyst@test.com",
      password: "StrongPassword1!",
      mfa_code: "246810",
    }),
  });
  if (reactivatedLogin.role !== "mfi_analyst") {
    throw new Error("Expected reactivated analyst login to succeed");
  }
  const repeatedReactivatedAnalyst = await api.request(
    `/admin/users/${encodeURIComponent("new-analyst@test.com")}/reactivate`,
    { method: "POST" },
    adminSession,
  );
  if (!repeatedReactivatedAnalyst.was_already_active) {
    throw new Error("Expected repeated staff reactivation to be idempotent");
  }

  const staffInvite = await api.request(
    "/admin/staff-invites",
    {
      method: "POST",
      body: JSON.stringify({
        email: "invited-analyst@test.com",
        role: "mfi_analyst",
        organization_id: "pavlodar-demo-mfi",
        expires_in_hours: 24,
      }),
    },
    adminSession,
  );
  if (
    !staffInvite.token
    || !staffInvite.invite_url
    || !staffInvite.token_id
    || !staffInvite.token_preview
    || !staffInvite.expires_at
    || staffInvite.accepted_at
  ) {
    throw new Error("Expected expiring staff invite one-time token and URL before acceptance");
  }
  if (staffInvite.invite_url.includes(staffInvite.token_id) || !staffInvite.invite_url.includes(staffInvite.token)) {
    throw new Error("Expected invite URL to contain only the one-time raw token");
  }
  const securityReadinessBeforeDelivery = await api.request("/admin/security/readiness", {}, adminSession);
  if (!securityReadinessBeforeDelivery.checks.some((check) => check.key === "invite_delivery" && check.status === "blocker")) {
    throw new Error("Expected undelivered pending invite to block delivery readiness");
  }
  const identityReadinessBeforeDelivery = await api.request("/admin/security/identity-readiness", {}, adminSession);
  if (
    identityReadinessBeforeDelivery.status !== "blocked"
    || !identityReadinessBeforeDelivery.production_blockers?.some((row) => row.key === "invite_delivery")
    || !identityReadinessBeforeDelivery.components?.some((row) => row.key === "invite_delivery" && row.status === "blocker")
  ) {
    throw new Error("Expected identity readiness room to surface undelivered invite blocker");
  }
  const inviteDeliveryReadinessBeforeDelivery = await api.request("/admin/staff-invites/delivery-readiness", {}, adminSession);
  if (
    inviteDeliveryReadinessBeforeDelivery.undelivered_active_invite_count < 1
    || !inviteDeliveryReadinessBeforeDelivery.production_blockers?.some((row) => row.key === "undelivered_active_invites")
  ) {
    throw new Error("Expected invite delivery readiness to surface undelivered invite blocker");
  }
  const deliveredInvite = await api.request(
    `/admin/staff-invites/${encodeURIComponent(staffInvite.token_id)}/delivery`,
    {
      method: "POST",
      body: JSON.stringify({ channel: "manual_copy" }),
    },
    adminSession,
  );
  if (
    !deliveredInvite.delivered_at
    || deliveredInvite.delivered_by !== "admin@test.com"
    || deliveredInvite.delivery_channel !== "manual_copy"
    || deliveredInvite.delivery_url_base !== "https://alex-tereshkovv.github.io/micro-score"
    || deliveredInvite.delivery_attempt_count !== 1
    || deliveredInvite.delivery_attempt?.provider !== "manual_receipt"
    || deliveredInvite.delivery_attempt?.status !== "sent"
  ) {
    throw new Error("Expected audited staff invite delivery metadata");
  }
  const repeatedDelivery = await api.request(
    `/admin/staff-invites/${encodeURIComponent(staffInvite.token_id)}/delivery`,
    { method: "POST", body: JSON.stringify({ channel: "manual_copy" }) },
    adminSession,
  );
  if (!repeatedDelivery.was_already_delivered) {
    throw new Error("Expected repeated invite delivery to be idempotent");
  }
  if (repeatedDelivery.delivery_attempt_count !== 2) {
    throw new Error("Expected repeated invite delivery to append an attempt");
  }
  const deliveryAttempts = await api.request(
    `/admin/staff-invites/${encodeURIComponent(staffInvite.token_id)}/delivery-attempts`,
    {},
    adminSession,
  );
  if (
    deliveryAttempts.length !== 2
    || !deliveryAttempts.every((attempt) => attempt.provider === "manual_receipt")
    || deliveryAttempts.some((attempt) => Object.values(attempt).includes(staffInvite.token))
  ) {
    throw new Error("Expected delivery attempts to hide raw tokens and preserve manual receipts");
  }
  const securityReadinessAfterDelivery = await api.request("/admin/security/readiness", {}, adminSession);
  if (!securityReadinessAfterDelivery.checks.some((check) => check.key === "invite_delivery" && check.status === "pass")) {
    throw new Error("Expected delivered pending invite to pass delivery readiness");
  }
  const failedDeliveryInvite = await api.request(
    "/admin/staff-invites",
    {
      method: "POST",
      body: JSON.stringify({
        email: "failed-delivery-analyst@test.com",
        role: "mfi_analyst",
        organization_id: "pavlodar-demo-mfi",
        expires_in_hours: 72,
        queue_delivery: true,
        delivery_channel: "email",
        delivery_recipient: "failed-delivery-analyst@test.com",
        delivery_provider: "local_fail",
      }),
    },
    adminSession,
  );
  if (
    failedDeliveryInvite.delivered_at
    || failedDeliveryInvite.delivery_attempt_count !== 1
    || failedDeliveryInvite.last_delivery_status !== "failed"
    || failedDeliveryInvite.last_delivery_provider !== "local_fail"
    || failedDeliveryInvite.delivery_attempt?.status !== "failed"
    || failedDeliveryInvite.delivery_attempt?.provider !== "local_fail"
    || !String(failedDeliveryInvite.delivery_attempt?.error || "").includes("simulated failure")
  ) {
    throw new Error("Expected local_fail provider to record a failed undelivered attempt");
  }
  const failedDeliveryReadiness = await api.request("/admin/security/readiness", {}, adminSession);
  if (!failedDeliveryReadiness.checks.some((check) => check.key === "invite_delivery" && check.status === "blocker")) {
    throw new Error("Expected failed invite delivery to keep delivery readiness blocked");
  }
  if (!failedDeliveryReadiness.checks.some((check) => check.key === "invite_delivery_attempts" && check.status === "warning")) {
    throw new Error("Expected failed invite delivery attempt to raise readiness warning");
  }
  const retriedDeliveryInvite = await api.request(
    `/admin/staff-invites/${encodeURIComponent(failedDeliveryInvite.token_id)}/delivery-attempts/retry`,
    {
      method: "POST",
      body: JSON.stringify({ channel: "email", provider: "local_outbox" }),
    },
    adminSession,
  );
  if (
    !retriedDeliveryInvite.delivered_at
    || retriedDeliveryInvite.was_already_delivered
    || retriedDeliveryInvite.delivery_attempt_count !== 2
    || retriedDeliveryInvite.last_delivery_status !== "sent"
    || retriedDeliveryInvite.last_delivery_provider !== "local_outbox"
    || retriedDeliveryInvite.delivery_attempt?.status !== "sent"
  ) {
    throw new Error("Expected retry delivery to append a sent attempt and mark invite delivered");
  }
  const retriedDeliveryAttempts = await api.request(
    `/admin/staff-invites/${encodeURIComponent(failedDeliveryInvite.token_id)}/delivery-attempts`,
    {},
    adminSession,
  );
  if (
    retriedDeliveryAttempts.length !== 2
    || retriedDeliveryAttempts[0].status !== "sent"
    || retriedDeliveryAttempts[1].status !== "failed"
    || retriedDeliveryAttempts.some((attempt) => Object.values(attempt).includes(failedDeliveryInvite.token))
  ) {
    throw new Error("Expected retried delivery attempts to preserve failed and sent statuses without raw token leakage");
  }
  const retriedDeliveryReadiness = await api.request("/admin/security/readiness", {}, adminSession);
  if (!retriedDeliveryReadiness.checks.some((check) => check.key === "invite_delivery_attempts" && check.status === "pass")) {
    throw new Error("Expected retry to clear failed delivery attempt warning");
  }
  let weakInvitePasswordRejected = false;
  try {
    await api.request("/auth/accept-staff-invite", {
      method: "POST",
      body: JSON.stringify({
        token: staffInvite.token,
        password: "password123",
        mfa_code: "246810",
      }),
    });
  } catch (error) {
    weakInvitePasswordRejected = String(error.message).includes("registration policy");
  }
  if (!weakInvitePasswordRejected) {
    throw new Error("Expected staff invite acceptance to enforce password policy");
  }
  const inviteAuth = await api.request("/auth/accept-staff-invite", {
    method: "POST",
    body: JSON.stringify({
      token: staffInvite.token,
      password: "StrongPassword1!",
      mfa_code: "246810",
    }),
  });
  if (
    inviteAuth.role !== "mfi_analyst"
    || inviteAuth.organization_id !== "pavlodar-demo-mfi"
    || !inviteAuth.session_expires_at
  ) {
    throw new Error("Expected accepted staff invite to create an analyst session");
  }
  const staffInvites = await api.request("/admin/staff-invites", {}, adminSession);
  if (staffInvites.some((invite) => invite.token)) {
    throw new Error("Expected staff invite list to hide one-time raw tokens");
  }
  if (!staffInvites.some((invite) => invite.token_id === staffInvite.token_id && invite.accepted_at && invite.delivered_at)) {
    throw new Error("Expected accepted staff invite in admin invite list");
  }
  let acceptedInviteRevokeRejected = false;
  try {
    await api.request(
      `/admin/staff-invites/${encodeURIComponent(staffInvite.token_id)}`,
      { method: "DELETE" },
      adminSession,
    );
  } catch (error) {
    acceptedInviteRevokeRejected = String(error.message).includes("cannot be revoked");
  }
  if (!acceptedInviteRevokeRejected) {
    throw new Error("Expected accepted staff invite revoke to be rejected");
  }
  let acceptedInviteRotateRejected = false;
  try {
    await api.request(
      `/admin/staff-invites/${encodeURIComponent(staffInvite.token_id)}/rotate`,
      {
        method: "POST",
        body: JSON.stringify({ expires_in_hours: 24 }),
      },
      adminSession,
    );
  } catch (error) {
    acceptedInviteRotateRejected = String(error.message).includes("cannot be rotated");
  }
  if (!acceptedInviteRotateRejected) {
    throw new Error("Expected accepted staff invite rotation to be rejected");
  }

  const rotateInvite = await api.request(
    "/admin/staff-invites",
    {
      method: "POST",
      body: JSON.stringify({
        email: "rotated-analyst@test.com",
        role: "mfi_analyst",
        organization_id: "pavlodar-demo-mfi",
        expires_in_hours: 24,
      }),
    },
    adminSession,
  );
  const rotatedInvite = await api.request(
    `/admin/staff-invites/${encodeURIComponent(rotateInvite.token_id)}/rotate`,
    {
      method: "POST",
      body: JSON.stringify({
        expires_in_hours: 72,
        queue_delivery: true,
        delivery_channel: "email",
        delivery_recipient: "rotated-analyst@test.com",
      }),
    },
    adminSession,
  );
  if (
    rotatedInvite.email !== rotateInvite.email
    || rotatedInvite.token_id === rotateInvite.token_id
    || rotatedInvite.token === rotateInvite.token
    || !String(rotatedInvite.invite_url || "").includes(rotatedInvite.token)
    || String(rotatedInvite.invite_url || "").includes(rotateInvite.token)
    || !rotatedInvite.delivered_at
    || rotatedInvite.delivery_attempt_count !== 1
    || rotatedInvite.delivery_attempt?.provider !== "local_outbox"
  ) {
    throw new Error("Expected staff invite rotation to issue a new one-time URL only");
  }
  let oldRotatedInviteRejected = false;
  try {
    await api.request("/auth/accept-staff-invite", {
      method: "POST",
      body: JSON.stringify({
        token: rotateInvite.token,
        password: "StrongPassword1!",
        mfa_code: "246810",
      }),
    });
  } catch (error) {
    oldRotatedInviteRejected = String(error.message).includes("revoked");
  }
  if (!oldRotatedInviteRejected) {
    throw new Error("Expected old rotated invite token to be revoked");
  }
  const invitesAfterRotation = await api.request("/admin/staff-invites", {}, adminSession);
  if (!invitesAfterRotation.some((invite) => invite.token_id === rotateInvite.token_id && invite.revoked_at)) {
    throw new Error("Expected rotated source invite to be closed");
  }
  if (!invitesAfterRotation.some((invite) => (
    invite.token_id === rotatedInvite.token_id
    && !invite.token
    && invite.delivered_at
    && invite.delivery_attempt_count === 1
    && invite.last_delivery_provider === "local_outbox"
  ))) {
    throw new Error("Expected rotated invite list row to hide raw token and show local outbox delivery");
  }
  const rotatedDeliveryAttempts = await api.request(
    `/admin/staff-invites/${encodeURIComponent(rotatedInvite.token_id)}/delivery-attempts`,
    {},
    adminSession,
  );
  if (rotatedDeliveryAttempts.length !== 1 || rotatedDeliveryAttempts[0].provider !== "local_outbox") {
    throw new Error("Expected rotated invite to expose local outbox delivery attempt");
  }
  let duplicateRotationRejected = false;
  try {
    await api.request(
      `/admin/staff-invites/${encodeURIComponent(rotateInvite.token_id)}/rotate`,
      {
        method: "POST",
        body: JSON.stringify({ expires_in_hours: 48 }),
      },
      adminSession,
    );
  } catch (error) {
    duplicateRotationRejected = String(error.message).includes("Active staff invite already exists");
  }
  if (!duplicateRotationRejected) {
    throw new Error("Expected duplicate active invite rotation to be rejected");
  }

  const revokeInvite = await api.request(
    "/admin/staff-invites",
    {
      method: "POST",
      body: JSON.stringify({
        email: "revoked-analyst@test.com",
        role: "mfi_analyst",
        organization_id: "pavlodar-demo-mfi",
        expires_in_hours: 24,
      }),
    },
    adminSession,
  );
  const revokedInvite = await api.request(
    `/admin/staff-invites/${encodeURIComponent(revokeInvite.token_id)}`,
    { method: "DELETE" },
    adminSession,
  );
  if (!revokedInvite.revoked_at || revokedInvite.revoked_by !== "admin@test.com") {
    throw new Error("Expected revoked staff invite metadata");
  }
  let revokedInviteAcceptanceRejected = false;
  try {
    await api.request("/auth/accept-staff-invite", {
      method: "POST",
      body: JSON.stringify({
        token: revokeInvite.token,
        password: "StrongPassword1!",
        mfa_code: "246810",
      }),
    });
  } catch (error) {
    revokedInviteAcceptanceRejected = String(error.message).includes("revoked");
  }
  if (!revokedInviteAcceptanceRejected) {
    throw new Error("Expected revoked staff invite acceptance to fail");
  }
  await api.request(
    "/admin/staff-invites",
    {
      method: "POST",
      body: JSON.stringify({
        email: "soon-expiring-analyst@test.com",
        role: "mfi_analyst",
        organization_id: "pavlodar-demo-mfi",
        expires_in_hours: 1,
      }),
    },
    adminSession,
  );
  const inviteHealth = await api.request("/admin/staff-invites/health", {}, adminSession);
  if (
    inviteHealth.status !== "attention"
    || inviteHealth.expiring_soon_count < 1
    || inviteHealth.action_required_count < 1
    || inviteHealth.window_hours !== 24
  ) {
    throw new Error("Expected staff invite health to flag soon-expiring pending invites");
  }
  const securityReadinessAfterInvite = await api.request("/admin/security/readiness", {}, adminSession);
  if (!securityReadinessAfterInvite.checks.some((check) => check.key === "invite_hygiene" && check.status === "blocker")) {
    throw new Error("Expected security readiness to include invite hygiene blocker");
  }
  const adminAudit = await api.request("/admin/audit-events", {}, adminSession);
  if (!adminAudit.some((event) => event.action === "staff_user_created")) {
    throw new Error("Expected staff provisioning audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_mfa_attested")) {
    throw new Error("Expected staff MFA attestation audit event");
  }
  const mfaFailureEvents = adminAudit.filter((event) => event.action === "staff_mfa_challenge_failed");
  if (!mfaFailureEvents.some((event) => event.details?.reason === "missing_attestation" && event.details?.source === "login")) {
    throw new Error("Expected failed staff MFA challenge audit event");
  }
  if (mfaFailureEvents.some((event) => Object.values(event.details || {}).includes("246810"))) {
    throw new Error("Expected failed staff MFA challenge audit event to hide raw MFA codes");
  }
  if (!adminAudit.some((event) => event.action === "staff_invite_created")) {
    throw new Error("Expected staff invite creation audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_invite_delivered")) {
    throw new Error("Expected staff invite delivery audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_invite_delivery_attempted")) {
    throw new Error("Expected staff invite delivery attempt audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_invite_rotated")) {
    throw new Error("Expected staff invite rotation audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_invite_accepted")) {
    throw new Error("Expected staff invite acceptance audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_invite_revoked")) {
    throw new Error("Expected staff invite revocation audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_user_disabled")) {
    throw new Error("Expected staff disable audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_session_revoked")) {
    throw new Error("Expected staff session revoke audit event");
  }
  if (!adminAudit.some((event) => event.action === "staff_user_reactivated")) {
    throw new Error("Expected staff reactivation audit event");
  }

  const modelVersionsBefore = await api.request("/admin/model-versions", {}, adminSession);
  const activeBefore = modelVersionsBefore.find((model) => model.is_active);
  const candidate = modelVersionsBefore.find((model) => model.lifecycle_status === "candidate");
  if (activeBefore?.version !== "static-demo-v1" || !candidate) {
    throw new Error("Expected active and candidate model registry entries");
  }
  await api.request(
    `/admin/model-versions/${encodeURIComponent(candidate.version)}/activate`,
    { method: "POST" },
    adminSession,
  );
  const stalePacket = await api.request(
    `/mfi/applications/${scored.id}/review-packet`,
    {},
    session,
  );
  if (!stalePacket.governance_flags.includes("stale_model_version")) {
    throw new Error("Expected previous score to be stale after model activation");
  }
  const rescored = await api.request(
    `/mfi/applications/${scored.id}/score`,
    { method: "POST" },
    session,
  );
  if (rescored.score_result.model_version !== candidate.version) {
    throw new Error("Expected scoring to use the newly active model version");
  }
  const currentPacket = await api.request(
    `/mfi/applications/${scored.id}/review-packet`,
    {},
    session,
  );
  if (currentPacket.governance_flags.includes("stale_model_version")) {
    throw new Error("Expected re-scored application to use the current active model");
  }

  await api.request(
    "/admin/organizations",
    {
      method: "POST",
      body: JSON.stringify({
        id: "pavlodar-second-mfi",
        name: "Pavlodar Second MFI",
        region: "Pavlodar region, Kazakhstan",
      }),
    },
    adminSession,
  );
  await api.request(
    "/admin/users",
    {
      method: "POST",
      body: JSON.stringify({
        email: "second-analyst@test.com",
        password: "StrongPassword1!",
        role: "mfi_analyst",
        organization_id: "pavlodar-second-mfi",
      }),
    },
    adminSession,
  );
  await api.request(
    `/admin/users/${encodeURIComponent("second-analyst@test.com")}/mfa/attest`,
    {
      method: "POST",
      body: JSON.stringify({ method: "pilot_attestation" }),
    },
    adminSession,
  );
  await api.request(
    "/applications",
    {
      method: "POST",
      body: JSON.stringify({
        requested_amount: 2750,
        organization_id: "pavlodar-second-mfi",
        consent_confirmed: true,
        consent_version: "synthetic-demo-v1",
        behavioral_signals: { annual_income: 42000, late_payment_count: 0 },
      }),
    },
    borrowerSession,
  );
  const secondAnalystAuth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "second-analyst@test.com",
      password: "StrongPassword1!",
      mfa_code: "246810",
    }),
  });
  const secondAnalystSession = {
    token: secondAnalystAuth.access_token,
    role: secondAnalystAuth.role,
    email: "second-analyst@test.com",
  };
  const firstTenantQueue = await api.request("/mfi/applications", {}, session);
  const secondTenantQueue = await api.request("/mfi/applications", {}, secondAnalystSession);
  if (firstTenantQueue.some((app) => app.organization_id !== "pavlodar-demo-mfi")) {
    throw new Error("First analyst queue leaked another organization");
  }
  if (
    secondTenantQueue.length !== 1 ||
    secondTenantQueue[0].organization_id !== "pavlodar-second-mfi"
  ) {
    throw new Error("Second analyst did not receive the isolated organization queue");
  }

  let missingConsentRejected = false;
  try {
    await api.request(
      "/applications",
      {
        method: "POST",
        body: JSON.stringify({ requested_amount: 2500, behavioral_signals: {} }),
      },
      borrowerSession,
    );
  } catch (error) {
    missingConsentRejected = String(error.message).includes("consent");
  }
  if (!missingConsentRejected) throw new Error("Expected missing consent to be rejected");

  let missingConsentVersionRejected = false;
  try {
    await api.request(
      "/applications",
      {
        method: "POST",
        body: JSON.stringify({
          requested_amount: 2500,
          consent_confirmed: true,
          behavioral_signals: {},
        }),
      },
      borrowerSession,
    );
  } catch (error) {
    missingConsentVersionRejected = String(error.message).includes("consent version");
  }
  if (!missingConsentVersionRejected) {
    throw new Error("Expected missing consent version to be rejected");
  }

  let sensitiveFieldRejected = false;
  try {
    await api.request(
      "/applications",
      {
        method: "POST",
        body: JSON.stringify({
          requested_amount: 2500,
          consent_confirmed: true,
          consent_version: "synthetic-demo-v1",
          behavioral_signals: { iin: "demo-value" },
        }),
      },
      borrowerSession,
    );
  } catch (error) {
    sensitiveFieldRejected = String(error.message).includes("behavioral_signals.iin");
  }
  if (!sensitiveFieldRejected) throw new Error("Expected sensitive field to be rejected");

  let mismatchedSettlementRejected = false;
  try {
    await api.request(
      "/applications",
      {
        method: "POST",
        body: JSON.stringify({
          requested_amount: 2500,
          district: "Aksu",
          settlement_type: "urban",
          organization_id: "pavlodar-demo-mfi",
          consent_confirmed: true,
          consent_version: "synthetic-demo-v1",
          behavioral_signals: {},
        }),
      },
      borrowerSession,
    );
  } catch (error) {
    mismatchedSettlementRejected = String(error.message).includes("industrial_city");
  }
  if (!mismatchedSettlementRejected) {
    throw new Error("Expected inconsistent district and settlement type to be rejected");
  }

  let unknownSignalRejected = false;
  try {
    await api.request(
      "/applications",
      {
        method: "POST",
        body: JSON.stringify({
          requested_amount: 2500,
          organization_id: "pavlodar-demo-mfi",
          consent_confirmed: true,
          consent_version: "synthetic-demo-v1",
          behavioral_signals: { unreviewed_proxy: 1 },
        }),
      },
      borrowerSession,
    );
  } catch (error) {
    unknownSignalRejected = String(error.message).includes("unreviewed_proxy");
  }
  if (!unknownSignalRejected) throw new Error("Expected unknown signal to be rejected");

  api.resetDemo();
  const resetApplications = await api.request("/mfi/applications", {}, session);
  if (resetApplications.length !== applications.length) {
    throw new Error("Expected reset demo portfolio to restore seeded applications");
  }

  const logout = await api.request("/auth/logout", { method: "POST" }, session);
  if (!logout.revoked) throw new Error("Expected static session to be revoked");
  let revokedSessionRejected = false;
  try {
    await api.request("/mfi/applications", {}, session);
  } catch (error) {
    revokedSessionRejected = String(error.message).includes("session expired");
  }
  if (!revokedSessionRejected) throw new Error("Expected revoked session to be rejected");

  console.log(
    JSON.stringify({
      mode: "static-demo-smoke",
      role: auth.role,
      applications: applications.length,
      risk_band: scored.score_result.risk_band,
      checklist_items: packet.checklist.length,
      policies: policies.policies.length,
      monte_carlo: true,
      portfolio_dashboard_v2: true,
      portfolio_settlement_rows: portfolioDashboard.settlementRows.length,
      simulation_iterations: simulation.assumptions.iterations,
      simulation_history: simulationHistory.length,
      borrower_history: borrowerHistory.length,
      borrower_terminal_status: borrowerTerminalDetail.status,
      action_plan_initial: draftPlan.stage,
      action_plan_review: reviewActionPlan.stage,
      action_plan_terminal: terminalPlan.stage,
      lifecycle_terminal_guard: terminalMutationRejected,
      risk_detail_v2: true,
      intake_contract_v2: true,
      csv_size: csv.size,
      privacy_guards: 3,
      registration_guards: 3,
      staff_provisioning: true,
      staff_invites: true,
      staff_invite_revocation: true,
      staff_invite_token_hygiene: true,
      staff_invite_delivery: true,
      staff_invite_delivery_readiness: true,
      staff_invite_delivery_outbox: true,
      staff_invite_delivery_provider: inviteDeliveryReadinessInitial.configured_provider,
      staff_invite_delivery_retry: true,
      staff_invite_rotation: true,
      staff_invite_health: true,
      mfa_readiness: true,
      mfa_challenge_monitoring: true,
      security_readiness: true,
      identity_readiness: true,
      identity_provider_mode: identityReadinessInitial.auth_provider_mode,
      staff_session_control: true,
      staff_user_disable: true,
      staff_user_reactivation: true,
      model_registry: true,
      active_model: rescored.score_result.model_version,
      tenant_isolation: true,
      logout_guard: true,
      session_expiry_visible: true,
      reset_applications: resetApplications.length,
    }),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
