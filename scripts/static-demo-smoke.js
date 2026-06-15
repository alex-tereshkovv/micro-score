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

  api.resetDemo();
  const resetApplications = await api.request("/mfi/applications", {}, session);
  if (resetApplications.length !== applications.length) {
    throw new Error("Expected reset demo portfolio to restore seeded applications");
  }

  console.log(
    JSON.stringify({
      mode: "static-demo-smoke",
      role: auth.role,
      applications: applications.length,
      risk_band: scored.score_result.risk_band,
      checklist_items: packet.checklist.length,
      policies: policies.policies.length,
      csv_size: csv.size,
      reset_applications: resetApplications.length,
    }),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
