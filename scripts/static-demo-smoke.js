const fs = require("fs");
const vm = require("vm");

global.window = {};
vm.runInThisContext(fs.readFileSync("apps/web/mock-api.js", "utf8"));

async function main() {
  const api = window.MicroScoreMockApi;
  if (!api) throw new Error("MicroScoreMockApi was not registered");

  const auth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "analyst@test.com",
      password: "password123",
    }),
  });
  const session = {
    token: auth.access_token,
    role: auth.role,
    email: "analyst@test.com",
  };

  const applications = await api.request("/mfi/applications", {}, session);
  if (applications.length < 3) {
    throw new Error(`Expected seeded applications, got ${applications.length}`);
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

  const policies = await api.request("/mfi/analytics/policies", {}, session);
  if (policies.policies.length < 3) {
    throw new Error("Expected multiple policy scenarios");
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
    }),
  });
  const adminSession = {
    token: adminAuth.access_token,
    role: adminAuth.role,
    email: "admin@test.com",
  };
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
  const adminAudit = await api.request("/admin/audit-events", {}, adminSession);
  if (!adminAudit.some((event) => event.action === "staff_user_created")) {
    throw new Error("Expected staff provisioning audit event");
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
      csv_size: csv.size,
      privacy_guards: 3,
      registration_guards: 3,
      staff_provisioning: true,
      tenant_isolation: true,
      logout_guard: true,
      reset_applications: resetApplications.length,
    }),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
