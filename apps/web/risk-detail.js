(function registerRiskDetail(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.MicroScoreRiskDetail = api;
}(typeof globalThis !== "undefined" ? globalThis : window, () => {
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
    };
  }

  return { summarizeReviewPacket };
}));
