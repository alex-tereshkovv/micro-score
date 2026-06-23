(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MicroScorePortfolioDashboard = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const RISK_BANDS = ["low", "medium", "high"];
  const SETTLEMENT_ORDER = ["urban", "industrial_city", "peri_urban", "rural", "unknown"];
  const CONTEXTUAL_SETTLEMENTS = new Set(["rural", "peri_urban"]);

  function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function average(values) {
    const clean = values.map(finiteNumber).filter((value) => value !== null);
    if (!clean.length) return null;
    return clean.reduce((total, value) => total + value, 0) / clean.length;
  }

  function scoredApplications(applications) {
    return (applications || []).filter((application) => (
      application
      && application.score_result
      && finiteNumber(application.score_result.high_risk_probability) !== null
    ));
  }

  function safeKey(value) {
    const key = String(value || "").trim();
    return key || "unknown";
  }

  function sortByRiskThenCount(left, right) {
    return (
      Number(right.avgRisk || 0) - Number(left.avgRisk || 0)
      || Number(right.count || 0) - Number(left.count || 0)
      || String(left.key).localeCompare(String(right.key))
    );
  }

  function sortByCountThenRisk(left, right) {
    return (
      Number(right.count || 0) - Number(left.count || 0)
      || Number(right.avgRisk || 0) - Number(left.avgRisk || 0)
      || String(left.key).localeCompare(String(right.key))
    );
  }

  function orderedSort(order) {
    const orderMap = new Map(order.map((item, index) => [item, index]));
    return (left, right) => (
      (orderMap.get(left.key) ?? order.length) - (orderMap.get(right.key) ?? order.length)
      || sortByCountThenRisk(left, right)
    );
  }

  function portfolioSegmentRows(scored, getKey, options = {}) {
    const total = scored.length;
    if (!total) return [];

    const groups = new Map();
    scored.forEach((application) => {
      const key = safeKey(getKey(application));
      const current = groups.get(key) || { key, count: 0, probabilities: [] };
      current.count += 1;
      current.probabilities.push(application.score_result.high_risk_probability);
      groups.set(key, current);
    });

    const rows = Array.from(groups.values()).map((row) => ({
      key: row.key,
      count: row.count,
      share: row.count / total,
      avgRisk: average(row.probabilities),
    }));

    const sortRows = options.sort === "count"
      ? sortByCountThenRisk
      : options.order
        ? orderedSort(options.order)
        : sortByRiskThenCount;

    rows.sort(sortRows);
    return typeof options.limit === "number" ? rows.slice(0, options.limit) : rows;
  }

  function riskBandRows(scored) {
    const counts = Object.fromEntries(RISK_BANDS.map((band) => [band, 0]));
    scored.forEach((application) => {
      const band = safeKey(application.score_result.risk_band);
      counts[band] = (counts[band] || 0) + 1;
    });
    const total = scored.length;
    return RISK_BANDS.map((band) => ({
      key: band,
      count: counts[band] || 0,
      share: total ? (counts[band] || 0) / total : 0,
    }));
  }

  function summarizePortfolioDashboard(applications) {
    const applicationList = applications || [];
    const scored = scoredApplications(applicationList);
    const probabilities = scored.map((application) => application.score_result.high_risk_probability);
    const districtRows = portfolioSegmentRows(
      scored,
      (application) => application.district || application.behavioral_signals?.pavlodar_district,
      { limit: 7 },
    );
    const allDistrictRows = portfolioSegmentRows(
      scored,
      (application) => application.district || application.behavioral_signals?.pavlodar_district,
      { sort: "count" },
    );
    const settlementRows = portfolioSegmentRows(
      scored,
      (application) => application.settlement_type || application.behavioral_signals?.settlement_type,
      { order: SETTLEMENT_ORDER },
    );
    const contextualSettlementCount = settlementRows
      .filter((row) => CONTEXTUAL_SETTLEMENTS.has(row.key))
      .reduce((total, row) => total + row.count, 0);

    return {
      applicationCount: applicationList.length,
      scoredCount: scored.length,
      avgRisk: average(probabilities),
      highRiskShare: scored.length
        ? scored.filter((application) => application.score_result.risk_band === "high").length / scored.length
        : 0,
      contextualSettlementShare: scored.length ? contextualSettlementCount / scored.length : 0,
      topDistrict: allDistrictRows[0] || null,
      riskBandRows: riskBandRows(scored),
      districtRows,
      settlementRows,
    };
  }

  return {
    CONTEXTUAL_SETTLEMENTS,
    RISK_BANDS,
    SETTLEMENT_ORDER,
    average,
    portfolioSegmentRows,
    scoredApplications,
    summarizePortfolioDashboard,
  };
});
