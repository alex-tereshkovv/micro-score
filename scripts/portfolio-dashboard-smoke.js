const fs = require("fs");
const vm = require("vm");

const dashboard = require("../apps/web/portfolio-dashboard.js");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function main() {
  const sample = [
    {
      district: "Pavlodar city",
      settlement_type: "urban",
      score_result: { risk_band: "low", high_risk_probability: 0.18 },
    },
    {
      district: "Bayanaul",
      settlement_type: "rural",
      score_result: { risk_band: "high", high_risk_probability: 0.82 },
    },
    {
      district: "Aksu",
      settlement_type: "industrial_city",
      score_result: { risk_band: "medium", high_risk_probability: 0.44 },
    },
    {
      district: "Pavlodar district",
      settlement_type: "peri_urban",
      score_result: { risk_band: "medium", high_risk_probability: 0.51 },
    },
    {
      district: "Pavlodar city",
      settlement_type: "urban",
      score_result: { risk_band: "low", high_risk_probability: 0.22 },
    },
    {
      district: "Irtysh",
      settlement_type: "rural",
    },
  ];
  const summary = dashboard.summarizePortfolioDashboard(sample);
  assert(summary.applicationCount === 6, "Expected full application count");
  assert(summary.scoredCount === 5, "Expected only scored applications to drive risk charts");
  assert(summary.riskBandRows.find((row) => row.key === "high").count === 1, "Expected high-risk row");
  assert(summary.districtRows[0].key === "Bayanaul", "Expected district rows to sort by average risk");
  assert(summary.topDistrict.key === "Pavlodar city", "Expected top district by concentration");
  assert(summary.settlementRows.map((row) => row.key).join(",") === "urban,industrial_city,peri_urban,rural", "Expected stable settlement ordering");
  assert(Math.abs(summary.contextualSettlementShare - 0.4) < 0.0001, "Expected rural/peri contextual share");

  global.window = {};
  window.MicroScoreApplicationIntake = require("../apps/web/application-intake.js");
  window.MicroScorePortfolioDashboard = dashboard;
  vm.runInThisContext(fs.readFileSync("apps/web/mock-api.js", "utf8"));

  const api = window.MicroScoreMockApi;
  const auth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "analyst@test.com",
      password: "password123",
      mfa_code: "246810",
    }),
  });
  const session = { token: auth.access_token, role: auth.role, email: "analyst@test.com" };
  const queue = await api.request("/mfi/applications", {}, session);
  const seeded = dashboard.summarizePortfolioDashboard(queue);
  const aksu = queue.find((application) => application.district === "Aksu");

  assert(seeded.applicationCount === queue.length, "Expected static queue application count");
  assert(seeded.scoredCount >= 3, "Expected seeded scored applications");
  assert(seeded.settlementRows.some((row) => row.key === "industrial_city"), "Expected industrial-city settlement row");
  assert(aksu?.settlement_type === "industrial_city", "Expected Aksu seed data to match intake contract");

  console.log(JSON.stringify({
    mode: "portfolio-dashboard-smoke",
    application_count: seeded.applicationCount,
    scored_count: seeded.scoredCount,
    settlement_rows: seeded.settlementRows.length,
    top_district: seeded.topDistrict?.key,
    contextual_settlement_share: Number(seeded.contextualSettlementShare.toFixed(4)),
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
