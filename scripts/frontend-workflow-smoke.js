const fs = require("fs");
const vm = require("vm");

const { summarizeReviewPacket } = require("../apps/web/risk-detail.js");

global.window = {};
window.MicroScoreApplicationIntake = require("../apps/web/application-intake.js");
vm.runInThisContext(fs.readFileSync("apps/web/mock-api.js", "utf8"));

async function login(api, email) {
  const payload = { email, password: "password123" };
  if (["analyst@test.com", "admin@test.com"].includes(email)) {
    payload.mfa_code = "246810";
  }
  const auth = await api.request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return { token: auth.access_token, role: auth.role, email };
}

async function main() {
  const api = window.MicroScoreMockApi;
  if (!api) throw new Error("Static frontend API was not registered");

  const analyst = await login(api, "analyst@test.com");
  const borrower = await login(api, "borrower@test.com");
  const borrowerHistory = await api.request("/applications", {}, borrower);
  if (!borrowerHistory.length || borrowerHistory.some((row) => row.score_result)) {
    throw new Error("Borrower history leaked internal score data");
  }

  const queue = await api.request("/mfi/applications", {}, analyst);
  const application = queue.find((row) => row.id === "static-demo-3");
  if (!application) throw new Error("Expected an open scored demo application");

  const initialPacket = await api.request(
    `/mfi/applications/${application.id}/review-packet`,
    {},
    analyst,
  );
  const initialView = summarizeReviewPacket(initialPacket);
  if (
    initialPacket.lifecycle.status !== "scored"
    || initialPacket.lifecycle.scoring_action !== "rescore"
    || initialPacket.affordability.completeness !== 1
    || initialView.decision_count !== 0
    || !initialView.allowed_decisions.includes("review")
  ) {
    throw new Error("Risk Detail v2 did not expose the initial review contract");
  }

  await api.request(
    `/mfi/applications/${application.id}/decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: "review",
        policy_name: "balanced_review",
        note: "Verify seasonal income.",
      }),
    },
    analyst,
  );
  const reviewPacket = await api.request(
    `/mfi/applications/${application.id}/review-packet`,
    {},
    analyst,
  );
  const reviewView = summarizeReviewPacket(reviewPacket);
  if (
    reviewPacket.lifecycle.status !== "under_review"
    || reviewView.decision_count !== 1
    || reviewView.allowed_decisions.includes("review")
    || reviewPacket.decision_history[0].note !== "Verify seasonal income."
  ) {
    throw new Error("Risk Detail v2 did not preserve manual-review history");
  }

  await api.request(
    `/mfi/applications/${application.id}/decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: "approve",
        policy_name: "balanced_review",
        note: "Evidence verified.",
      }),
    },
    analyst,
  );
  const finalPacket = await api.request(
    `/mfi/applications/${application.id}/review-packet`,
    {},
    analyst,
  );
  const finalView = summarizeReviewPacket(finalPacket);
  if (
    !finalView.terminal
    || finalView.scoring_action !== null
    || finalView.decision_count !== 2
    || finalView.allowed_decisions.length
    || !finalView.readiness_label.startsWith("Finalized")
  ) {
    throw new Error("Risk Detail v2 did not lock the terminal decision state");
  }

  console.log(JSON.stringify({
    mode: "frontend-workflow-smoke",
    borrower_history: borrowerHistory.length,
    affordability_complete: initialView.affordability_complete,
    review_decisions: reviewView.decision_count,
    terminal_decisions: finalView.decision_count,
    terminal: finalView.terminal,
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
