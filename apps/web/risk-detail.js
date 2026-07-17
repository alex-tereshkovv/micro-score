(function registerRiskDetail(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.MicroScoreRiskDetail = api;
}(typeof globalThis !== "undefined" ? globalThis : window, () => {
  const DECISION_LABELS = {
    approve: "Approve",
    review: "Manual review",
    decline: "Decline",
  };

  function labelForDecision(decision) {
    return DECISION_LABELS[decision] || String(decision || "").replaceAll("_", " ");
  }

  function checklistBlockers(packet) {
    const checklist = Array.isArray(packet?.checklist) ? packet.checklist : [];
    return checklist
      .filter((item) => item.status === "required")
      .map((item) => ({
        code: item.code,
        title: item.title,
        evidence: item.evidence || null,
      }));
  }

  function buildReviewActionPlan(packet) {
    const lifecycle = packet?.lifecycle || {};
    const allowedDecisions = Array.isArray(lifecycle.allowed_decisions)
      ? [...lifecycle.allowed_decisions]
      : [];
    const blockers = checklistBlockers(packet);
    const blockerCodes = new Set(blockers.map((item) => item.code));
    const terminal = Boolean(lifecycle.terminal);
    const scoringAction = lifecycle.scoring_action || null;
    const hasScore = Boolean(packet?.model_summary);
    const decisionCount = Array.isArray(packet?.decision_history)
      ? packet.decision_history.length
      : 0;

    let stage = "review_ready";
    let title = "Ready for decision";
    let body = "Use the review packet, checklist, and available decision actions before recording the next workflow step.";
    let primaryLabel = "Record decision";
    const steps = [];

    if (terminal) {
      stage = "terminal_locked";
      title = "Terminal locked";
      body = "The application has a final MFI decision. Scoring and decision mutations are locked.";
      primaryLabel = "Locked";
      steps.push("No further scoring or decision changes are available.");
    } else if (!hasScore || scoringAction === "score") {
      stage = "score_first";
      title = "Score first";
      body = "Run the governed score before using the review packet for a human decision.";
      primaryLabel = "Score";
      steps.push("Generate the score and explanations.");
      steps.push("Reopen the review packet after scoring.");
    } else if (blockerCodes.has("rescore_current_model")) {
      stage = "rescore_required";
      title = "Rescore current model";
      body = "This packet was scored with an older model version. Refresh the score before decision review.";
      primaryLabel = "Rescore";
      steps.push("Refresh the score with the active model.");
      steps.push("Review the updated checklist and risk summary.");
    } else if (String(lifecycle.status || "") === "under_review") {
      stage = "finalize_decision";
      title = "Finalize decision";
      body = "Manual review is open. Record approve or decline after the required checks are addressed.";
      primaryLabel = "Finalize";
      steps.push("Resolve required checklist items.");
      steps.push("Record approve or decline with an analyst note.");
    } else if (allowedDecisions.includes("review")) {
      stage = "review_or_decide";
      title = "Review or decide";
      body = "The application is scored. Record manual review, approve, or decline according to the packet.";
      primaryLabel = "Record decision";
      steps.push("Inspect the checklist and governance flags.");
      steps.push("Choose one of the available decision actions.");
    } else if (!allowedDecisions.length) {
      stage = "blocked";
      title = "Action unavailable";
      body = lifecycle.status_note || "No decision action is available for the current lifecycle state.";
      primaryLabel = "Unavailable";
      steps.push("Refresh the selected application and review packet.");
    }

    return {
      stage,
      title,
      body,
      primary_label: primaryLabel,
      steps,
      blockers,
      blocker_count: blockers.length,
      terminal,
      scoring_action: scoringAction,
      score_enabled: Boolean(scoringAction) && !terminal,
      score_label: scoringAction === "rescore" ? "Rescore" : scoringAction === "score" ? "Score" : "Locked",
      decision_enabled: allowedDecisions.length > 0 && hasScore && !terminal,
      allowed_decisions: allowedDecisions,
      allowed_decision_labels: allowedDecisions.map(labelForDecision),
      decision_count: decisionCount,
    };
  }

  function summarizeReviewPacket(packet) {
    const checklist = Array.isArray(packet?.checklist) ? packet.checklist : [];
    const lifecycle = packet?.lifecycle || {};
    const requiredChecks = checklist.filter((item) => item.status === "required").length;
    const completedChecks = checklist.filter((item) => item.status === "complete").length;
    const decisionCount = Array.isArray(packet?.decision_history)
      ? packet.decision_history.length
      : 0;
    let readinessLabel;
    if (lifecycle.terminal) {
      readinessLabel = `Finalized: ${String(lifecycle.status || "decision").replaceAll("_", " ")}`;
    } else if (!packet?.model_summary) {
      readinessLabel = "Score required";
    } else if (requiredChecks) {
      readinessLabel = `${requiredChecks} required ${requiredChecks === 1 ? "check" : "checks"}`;
    } else {
      readinessLabel = "Ready for decision";
    }
    const actionPlan = buildReviewActionPlan(packet);
    return {
      readiness_label: readinessLabel,
      required_checks: requiredChecks,
      completed_checks: completedChecks,
      decision_count: decisionCount,
      terminal: Boolean(lifecycle.terminal),
      scoring_action: lifecycle.scoring_action || null,
      allowed_decisions: Array.isArray(lifecycle.allowed_decisions)
        ? [...lifecycle.allowed_decisions]
        : [],
      affordability_complete: Number(packet?.affordability?.completeness || 0) === 1,
      action_plan: actionPlan,
      action_stage: actionPlan.stage,
      blocker_count: actionPlan.blocker_count,
      decision_enabled: actionPlan.decision_enabled,
      score_enabled: actionPlan.score_enabled,
    };
  }

  return { buildReviewActionPlan, summarizeReviewPacket };
}));
