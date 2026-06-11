const state = {
  apiBase: localStorage.getItem("microscore.apiBase") || "http://127.0.0.1:8000",
  token: localStorage.getItem("microscore.token") || "",
  role: localStorage.getItem("microscore.role") || "",
  email: localStorage.getItem("microscore.email") || "",
  selectedApplicationId: "",
  applications: [],
  policyAnalytics: null,
  decisionAnalytics: null,
};

const els = {
  apiBase: document.querySelector("#apiBase"),
  apiStatus: document.querySelector("#apiStatus"),
  checkApiButton: document.querySelector("#checkApiButton"),
  roleTabs: document.querySelectorAll(".role-tab"),
  views: document.querySelectorAll(".view-grid"),
  viewTitle: document.querySelector("#viewTitle"),
  authForm: document.querySelector("#authForm"),
  registerButton: document.querySelector("#registerButton"),
  email: document.querySelector("#email"),
  password: document.querySelector("#password"),
  role: document.querySelector("#role"),
  sessionRole: document.querySelector("#sessionRole"),
  logoutButton: document.querySelector("#logoutButton"),
  messageArea: document.querySelector("#messageArea"),
  demoButtons: document.querySelectorAll("[data-demo]"),
  applicationForm: document.querySelector("#applicationForm"),
  fillDemoApplication: document.querySelector("#fillDemoApplication"),
  borrowerApplicationId: document.querySelector("#borrowerApplicationId"),
  loadBorrowerApplication: document.querySelector("#loadBorrowerApplication"),
  refreshBorrowerApplication: document.querySelector("#refreshBorrowerApplication"),
  borrowerApplicationCard: document.querySelector("#borrowerApplicationCard"),
  portfolioOverview: document.querySelector("#portfolioOverview"),
  refreshApplications: document.querySelector("#refreshApplications"),
  applicationsTable: document.querySelector("#applicationsTable"),
  scoreSelectedApplication: document.querySelector("#scoreSelectedApplication"),
  scoreDetail: document.querySelector("#scoreDetail"),
  decisionForm: document.querySelector("#decisionForm"),
  refreshAnalytics: document.querySelector("#refreshAnalytics"),
  segmentAnalytics: document.querySelector("#segmentAnalytics"),
  refreshPolicyAnalytics: document.querySelector("#refreshPolicyAnalytics"),
  policyNote: document.querySelector("#policyNote"),
  policyAnalytics: document.querySelector("#policyAnalytics"),
  policySegments: document.querySelector("#policySegments"),
  decisionAudit: document.querySelector("#decisionAudit"),
  refreshAudit: document.querySelector("#refreshAudit"),
  auditTrail: document.querySelector("#auditTrail"),
  clearApplications: document.querySelector("#clearApplications"),
};

const viewTitles = {
  borrowerView: "Borrower workspace",
  mfiView: "MFI analyst workspace",
  adminView: "Admin workspace",
};

const demoApplication = {
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
};

function saveSession() {
  localStorage.setItem("microscore.apiBase", state.apiBase);
  localStorage.setItem("microscore.token", state.token);
  localStorage.setItem("microscore.role", state.role);
  localStorage.setItem("microscore.email", state.email);
}

function clearSession() {
  state.token = "";
  state.role = "";
  state.email = "";
  saveSession();
  updateSessionStrip();
}

function updateSessionStrip() {
  if (state.token) {
    els.sessionRole.textContent = `${state.role} - ${state.email}`;
    els.sessionRole.classList.remove("muted");
  } else {
    els.sessionRole.textContent = "No session";
    els.sessionRole.classList.add("muted");
  }
}

function showMessage(text, type = "info") {
  els.messageArea.innerHTML = `<div class="message ${type}">${escapeHtml(text)}</div>`;
  window.clearTimeout(showMessage.timer);
  showMessage.timer = window.setTimeout(() => {
    els.messageArea.innerHTML = "";
  }, 5200);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "-";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value));
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatPolicyName(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function clampPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 0;
  return Math.max(0, Math.min(100, Number(value) * 100));
}

async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const response = await fetch(`${state.apiBase}${path}`, {
    ...options,
    headers,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    throw new Error(Array.isArray(detail) ? JSON.stringify(detail) : detail);
  }
  return data;
}

async function checkApi() {
  state.apiBase = els.apiBase.value.trim().replace(/\/$/, "");
  saveSession();
  els.apiStatus.textContent = "Checking API...";
  els.apiStatus.className = "status-line neutral";
  try {
    const health = await apiFetch("/health", { headers: {} });
    els.apiStatus.textContent = `${health.status} - ${health.service}`;
    els.apiStatus.className = "status-line ok";
  } catch (error) {
    els.apiStatus.textContent = `Offline - ${error.message}`;
    els.apiStatus.className = "status-line error";
  }
}

function switchView(viewId) {
  els.views.forEach((view) => view.classList.toggle("active-view", view.id === viewId));
  els.roleTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.view === viewId));
  els.viewTitle.textContent = viewTitles[viewId];
}

async function authenticate(mode) {
  const payload = {
    email: els.email.value.trim(),
    password: els.password.value,
  };
  if (mode === "register") payload.role = els.role.value;

  const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
  const auth = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.token = auth.access_token;
  state.role = auth.role;
  state.email = payload.email;
  saveSession();
  updateSessionStrip();
  showMessage(`Signed in as ${auth.role}`, "ok");
}

function fillDemoCredentials(email, role) {
  els.email.value = email;
  els.password.value = "password123";
  els.role.value = role;
}

function formNumber(form, name) {
  const raw = form.elements[name].value;
  return raw === "" ? undefined : Number(raw);
}

function fillApplicationForm(values) {
  Object.entries(values).forEach(([name, value]) => {
    if (els.applicationForm.elements[name]) {
      els.applicationForm.elements[name].value = value;
    }
  });
}

function applicationPayload() {
  const form = els.applicationForm;
  return {
    requested_amount: formNumber(form, "requested_amount"),
    purpose: form.elements.purpose.value.trim(),
    district: form.elements.district.value,
    settlement_type: form.elements.settlement_type.value,
    behavioral_signals: {
      annual_income: formNumber(form, "annual_income"),
      total_outstanding_debt: formNumber(form, "total_outstanding_debt"),
      mobile_banking_logins: formNumber(form, "mobile_banking_logins"),
      online_transfer_frequency: formNumber(form, "online_transfer_frequency"),
      atm_withdrawal_frequency: formNumber(form, "atm_withdrawal_frequency"),
      avg_deposit_amount: formNumber(form, "avg_deposit_amount"),
      debit_card_spending: formNumber(form, "debit_card_spending"),
      num_open_loans: formNumber(form, "num_open_loans"),
      late_payment_count: formNumber(form, "late_payment_count"),
      gender: form.elements.gender.value,
      employment_status: form.elements.employment_status.value,
    },
  };
}

function rememberApplication(id) {
  localStorage.setItem("microscore.lastApplicationId", id);
  els.borrowerApplicationId.value = id;
}

function resetApplicationViews() {
  localStorage.removeItem("microscore.lastApplicationId");
  state.selectedApplicationId = "";
  state.applications = [];
  state.policyAnalytics = null;
  state.decisionAnalytics = null;

  els.borrowerApplicationId.value = "";
  els.borrowerApplicationCard.className = "result-block empty";
  els.borrowerApplicationCard.textContent = "No application selected.";

  els.applicationsTable.className = "table-shell empty";
  els.applicationsTable.textContent = "No applications loaded.";

  els.scoreDetail.className = "result-block empty";
  els.scoreDetail.textContent = "Select an application.";
  els.decisionForm.reset();

  els.portfolioOverview.className = "portfolio-overview empty";
  els.portfolioOverview.textContent = "Load applications to view portfolio analytics.";

  els.segmentAnalytics.className = "table-shell empty";
  els.segmentAnalytics.textContent = "No segment analytics loaded.";

  els.policyNote.textContent = "Score applications to compare policies.";
  els.policyAnalytics.className = "policy-grid empty";
  els.policyAnalytics.textContent = "No policy analytics loaded.";
  els.policySegments.className = "table-shell empty";
  els.policySegments.textContent = "No segment policy analytics loaded.";
  els.decisionAudit.className = "table-shell empty";
  els.decisionAudit.textContent = "No decision audit loaded.";
}

function renderApplication(application) {
  const score = application.score_result;
  const riskClass = score ? `risk-${score.risk_band}` : "";
  const decision = renderRecordedDecision(application.decision_result);
  return `
    <div class="metric-grid">
      <div class="metric"><span>Status</span><strong>${escapeHtml(application.status)}</strong></div>
      <div class="metric"><span>Amount</span><strong>${formatMoney(application.requested_amount)}</strong></div>
      <div class="metric"><span>District</span><strong>${escapeHtml(application.district || "-")}</strong></div>
      <div class="metric"><span>Risk</span><strong class="${riskClass}">${score ? escapeHtml(score.risk_band) : "not scored"}</strong></div>
    </div>
    <p class="record-line"><strong>ID:</strong> ${escapeHtml(application.id)}</p>
    ${decision}
    ${score ? renderScore(score) : ""}
  `;
}

function renderRecordedDecision(decision) {
  if (!decision) return "";

  return `
    <div class="recorded-decision decision-${escapeHtml(decision.decision)}">
      <div>
        <span>MFI decision</span>
        <strong>${escapeHtml(formatPolicyName(decision.decision))}</strong>
      </div>
      <div>
        <span>Policy</span>
        <strong>${escapeHtml(formatPolicyName(decision.policy_name || "not recorded"))}</strong>
      </div>
      <p>${escapeHtml(decision.note || "No note recorded.")}</p>
    </div>
  `;
}

function renderScore(score) {
  const warnings = (score.warnings || [])
    .map((warning) => `<li>${escapeHtml(warning)}</li>`)
    .join("");
  const scenarios = renderScenarioScores(score);
  const decisionSupport = renderDecisionSupport(score.decision_support);
  const explanation = renderLocalExplanation(score.explanation, score.top_model_factors);
  return `
    <div class="metric-grid">
      <div class="metric"><span>Probability</span><strong>${formatPercent(score.high_risk_probability)}</strong></div>
      <div class="metric"><span>Model</span><strong>${escapeHtml(score.model_version)}</strong></div>
      <div class="metric"><span>Proxy sensitivity</span><strong>${formatPercent(score.proxy_sensitivity_delta)}</strong></div>
    </div>
    ${decisionSupport}
    ${scenarios}
    ${explanation}
    <ul class="warning-list">${warnings}</ul>
  `;
}

function renderFactorList(factors) {
  if (!factors?.length) return "<p class=\"empty tiny-text\">No factors available.</p>";

  return `
    <ul class="factor-list">
      ${factors
        .map(
          (factor) => `
            <li class="${factor.value >= 0 ? "factor-risk" : "factor-protective"}">
              <span>${escapeHtml(factor.feature)}</span>
              <strong>${Number(factor.value).toFixed(3)}</strong>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function renderLocalExplanation(explanation, fallbackFactors = []) {
  if (!explanation) {
    return `
      <div class="explanation-block">
        <h4>Local explanation</h4>
        ${renderFactorList(fallbackFactors || [])}
      </div>
    `;
  }

  return `
    <div class="explanation-block">
      <h4>Local explanation</h4>
      <div class="explanation-summary">
        <div><span>Method</span><strong>${escapeHtml(explanation.method)}</strong></div>
        <div><span>Model probability check</span><strong>${formatPercent(explanation.high_risk_probability)}</strong></div>
      </div>
      <div class="explanation-columns">
        <div>
          <span>Raises risk</span>
          ${renderFactorList(explanation.top_positive_factors || [])}
        </div>
        <div>
          <span>Lowers risk</span>
          ${renderFactorList(explanation.top_protective_factors || [])}
        </div>
      </div>
    </div>
  `;
}

function renderDecisionSupport(decisionSupport) {
  if (!decisionSupport) return "";

  const rationale = (decisionSupport.rationale || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const nextSteps = (decisionSupport.next_steps || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  return `
    <div class="decision-block">
      <h4>Recommendation</h4>
      <strong>${escapeHtml(decisionSupport.title)}</strong>
      <div class="decision-columns">
        <div>
          <span>Rationale</span>
          <ul>${rationale}</ul>
        </div>
        <div>
          <span>Next steps</span>
          <ul>${nextSteps}</ul>
        </div>
      </div>
    </div>
  `;
}

function renderScenarioScores(score) {
  const scenarios = score.scenario_scores || [];
  if (!scenarios.length) return "";

  const rows = scenarios
    .map(
      (scenario) => `
        <div class="scenario-row">
          <div>
            <strong>${escapeHtml(scenario.label)}</strong>
            <span>${escapeHtml(scenario.scenario)}</span>
          </div>
          <div>
            <strong class="risk-${escapeHtml(scenario.risk_band)}">${escapeHtml(scenario.risk_band)}</strong>
            <span>${formatPercent(scenario.high_risk_probability)}</span>
          </div>
        </div>
      `,
    )
    .join("");
  return `<div class="scenario-block"><h4>Scenario comparison</h4>${rows}</div>`;
}

async function submitApplication(event) {
  event.preventDefault();
  const application = await apiFetch("/applications", {
    method: "POST",
    body: JSON.stringify(applicationPayload()),
  });
  rememberApplication(application.id);
  els.borrowerApplicationCard.classList.remove("empty");
  els.borrowerApplicationCard.innerHTML = renderApplication(application);
  showMessage("Application submitted", "ok");
}

async function loadBorrowerApplication() {
  const id = els.borrowerApplicationId.value.trim();
  if (!id) {
    showMessage("Enter an application ID", "error");
    return;
  }
  const application = await apiFetch(`/applications/${encodeURIComponent(id)}`);
  els.borrowerApplicationCard.classList.remove("empty");
  els.borrowerApplicationCard.innerHTML = renderApplication(application);
}

function renderApplicationsTable(applications) {
  if (!applications.length) {
    els.applicationsTable.className = "table-shell empty";
    els.applicationsTable.textContent = "No applications loaded.";
    return;
  }
  els.applicationsTable.className = "table-shell";
  const rows = applications
    .map(
      (application) => `
        <tr class="selectable ${application.id === state.selectedApplicationId ? "selected" : ""}" data-application-id="${escapeHtml(application.id)}">
          <td>${escapeHtml(application.status)}</td>
          <td>${escapeHtml(application.borrower_email)}</td>
          <td>${formatMoney(application.requested_amount)}</td>
          <td>${escapeHtml(application.district || "-")}</td>
          <td>${application.score_result ? formatPercent(application.score_result.high_risk_probability) : "-"}</td>
          <td>${application.decision_result ? escapeHtml(formatPolicyName(application.decision_result.decision)) : "-"}</td>
        </tr>
      `,
    )
    .join("");
  els.applicationsTable.innerHTML = `
    <table>
      <thead><tr><th>Status</th><th>Borrower</th><th>Amount</th><th>District</th><th>Risk</th><th>Decision</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  els.applicationsTable.querySelectorAll("[data-application-id]").forEach((row) => {
    row.addEventListener("click", () => selectApplication(row.dataset.applicationId));
  });
}

function selectApplication(applicationId) {
  state.selectedApplicationId = applicationId;
  const application = state.applications.find((item) => item.id === applicationId);
  renderApplicationsTable(state.applications);
  els.scoreDetail.classList.remove("empty");
  els.scoreDetail.innerHTML = application ? renderApplication(application) : "Select an application.";
}

function scoredApplications(applications) {
  return applications.filter((application) => application.score_result);
}

function average(values) {
  if (!values.length) return null;
  return values.reduce((total, value) => total + Number(value), 0) / values.length;
}

function countBy(items, getKey) {
  return items.reduce((counts, item) => {
    const key = getKey(item) || "unknown";
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function renderPortfolioOverview() {
  if (!state.applications.length) {
    els.portfolioOverview.className = "portfolio-overview empty";
    els.portfolioOverview.textContent = "Load applications to view portfolio analytics.";
    return;
  }

  const scored = scoredApplications(state.applications);
  const probabilities = scored.map((application) => application.score_result.high_risk_probability);
  const avgRisk = average(probabilities);
  const highRiskShare = scored.length
    ? scored.filter((application) => application.score_result.risk_band === "high").length / scored.length
    : 0;
  const riskCounts = {
    low: 0,
    medium: 0,
    high: 0,
    ...countBy(scored, (application) => application.score_result.risk_band),
  };
  const districtRows = renderDistrictRiskRows(scored);
  const policySnapshot = renderPortfolioPolicySnapshot(state.policyAnalytics);
  const decisionSnapshot = renderPortfolioDecisionSnapshot(state.decisionAnalytics);

  els.portfolioOverview.className = "portfolio-overview";
  els.portfolioOverview.innerHTML = `
    <div class="portfolio-metrics">
      <div class="metric"><span>Applications</span><strong>${state.applications.length}</strong></div>
      <div class="metric"><span>Scored</span><strong>${scored.length}</strong></div>
      <div class="metric"><span>Avg risk</span><strong>${formatPercent(avgRisk)}</strong></div>
      <div class="metric"><span>High risk</span><strong class="risk-high">${formatPercent(highRiskShare)}</strong></div>
    </div>
    <div class="portfolio-grid">
      <section class="portfolio-card">
        <h4>Risk bands</h4>
        <div class="risk-band-chart">
          ${renderRiskBandBar("low", riskCounts.low, scored.length)}
          ${renderRiskBandBar("medium", riskCounts.medium, scored.length)}
          ${renderRiskBandBar("high", riskCounts.high, scored.length)}
        </div>
      </section>
      <section class="portfolio-card">
        <h4>District risk</h4>
        <div class="district-bars">${districtRows}</div>
      </section>
      <section class="portfolio-card portfolio-policy-card">
        <h4>Policy mix</h4>
        ${policySnapshot}
      </section>
      <section class="portfolio-card portfolio-decision-card">
        <h4>Analyst decisions</h4>
        ${decisionSnapshot}
      </section>
    </div>
  `;
}

function renderRiskBandBar(label, count, total) {
  const rate = total ? count / total : 0;
  return `
    <div class="risk-band-row">
      <div>
        <strong class="risk-${escapeHtml(label)}">${escapeHtml(label)}</strong>
        <span>${count} applications</span>
      </div>
      <div class="portfolio-bar">
        <span class="risk-fill-${escapeHtml(label)}" style="width: ${clampPercent(rate)}%"></span>
      </div>
      <em>${formatPercent(rate)}</em>
    </div>
  `;
}

function renderDistrictRiskRows(scored) {
  if (!scored.length) return "<p class=\"empty tiny-text\">No scored applications yet.</p>";

  const groups = {};
  scored.forEach((application) => {
    const district = application.district || application.behavioral_signals?.pavlodar_district || "unknown";
    groups[district] = groups[district] || [];
    groups[district].push(application.score_result.high_risk_probability);
  });

  return Object.entries(groups)
    .map(([district, values]) => ({
      district,
      n: values.length,
      avgRisk: average(values),
    }))
    .sort((left, right) => right.avgRisk - left.avgRisk || right.n - left.n)
    .slice(0, 7)
    .map(
      (row) => `
        <div class="district-risk-row">
          <div>
            <strong>${escapeHtml(row.district)}</strong>
            <span>${row.n} applications</span>
          </div>
          <div class="portfolio-bar">
            <span class="district-risk-fill" style="width: ${clampPercent(row.avgRisk)}%"></span>
          </div>
          <em>${formatPercent(row.avgRisk)}</em>
        </div>
      `,
    )
    .join("");
}

function renderPortfolioPolicySnapshot(payload) {
  const policies = payload?.policies || [];
  const policy = policies.find((item) => item.policy === "balanced_review") || policies[0];
  if (!policy) return "<p class=\"empty tiny-text\">Refresh Policy Lab to view policy mix.</p>";

  const approve = clampPercent(policy.auto_approval_rate);
  const review = clampPercent(policy.manual_review_rate);
  const decline = clampPercent(policy.auto_decline_rate);

  return `
    <div class="portfolio-policy-heading">
      <strong>${escapeHtml(formatPolicyName(policy.policy))}</strong>
      <span>${policy.n} scored applications</span>
    </div>
    <div class="policy-mix portfolio-policy-mix" aria-label="Balanced policy action mix">
      <span class="policy-approve" style="width: ${approve}%"></span>
      <span class="policy-review" style="width: ${review}%"></span>
      <span class="policy-decline" style="width: ${decline}%"></span>
    </div>
    <div class="portfolio-policy-legend">
      <div><span class="legend-dot approve-dot"></span>Approve <strong>${formatPercent(policy.auto_approval_rate)}</strong></div>
      <div><span class="legend-dot review-dot"></span>Review <strong>${formatPercent(policy.manual_review_rate)}</strong></div>
      <div><span class="legend-dot decline-dot"></span>Decline <strong>${formatPercent(policy.auto_decline_rate)}</strong></div>
    </div>
  `;
}

function renderPortfolioDecisionSnapshot(payload) {
  if (!payload?.decided_application_count) {
    return "<p class=\"empty tiny-text\">No analyst decisions recorded yet.</p>";
  }

  const rows = payload.decision_rows || [];
  const decided = payload.decided_application_count;
  return `
    <div class="portfolio-policy-heading">
      <strong>${decided} recorded</strong>
      <span>${payload.application_count} applications</span>
    </div>
    <div class="decision-bars">
      ${rows.map(renderDecisionBar).join("")}
    </div>
  `;
}

function renderDecisionBar(row) {
  return `
    <div class="decision-bar-row">
      <div>
        <strong class="decision-text-${escapeHtml(row.decision)}">${escapeHtml(formatPolicyName(row.decision))}</strong>
        <span>${row.count} applications</span>
      </div>
      <div class="portfolio-bar">
        <span class="decision-fill-${escapeHtml(row.decision)}" style="width: ${clampPercent(row.rate)}%"></span>
      </div>
      <em>${formatPercent(row.rate)}</em>
    </div>
  `;
}

async function refreshApplications() {
  state.applications = await apiFetch("/mfi/applications");
  if (!state.selectedApplicationId && state.applications.length) {
    state.selectedApplicationId = state.applications[0].id;
  }
  renderApplicationsTable(state.applications);
  if (state.selectedApplicationId) selectApplication(state.selectedApplicationId);
  renderPortfolioOverview();
  await refreshAnalytics();
  await refreshPolicyAnalytics();
  await refreshDecisionAnalytics();
}

async function scoreSelectedApplication() {
  if (!state.selectedApplicationId) {
    showMessage("Select an application first", "error");
    return;
  }
  const scored = await apiFetch(`/mfi/applications/${encodeURIComponent(state.selectedApplicationId)}/score`, {
    method: "POST",
  });
  state.applications = state.applications.map((item) => (item.id === scored.id ? scored : item));
  selectApplication(scored.id);
  await refreshAnalytics();
  await refreshPolicyAnalytics();
  showMessage("Application scored", "ok");
}

function decisionPayload() {
  const form = els.decisionForm;
  return {
    decision: form.elements.decision.value,
    policy_name: form.elements.policy_name.value,
    note: form.elements.note.value.trim(),
  };
}

async function saveApplicationDecision() {
  if (!state.selectedApplicationId) {
    showMessage("Select an application first", "error");
    return;
  }
  const selected = state.applications.find((item) => item.id === state.selectedApplicationId);
  if (!selected?.score_result) {
    showMessage("Score the application before saving a decision", "error");
    return;
  }

  const updated = await apiFetch(`/mfi/applications/${encodeURIComponent(state.selectedApplicationId)}/decision`, {
    method: "POST",
    body: JSON.stringify(decisionPayload()),
  });
  state.applications = state.applications.map((item) => (item.id === updated.id ? updated : item));
  selectApplication(updated.id);
  await refreshDecisionAnalytics();
  showMessage("MFI decision saved", "ok");
}

async function refreshAnalytics() {
  const rows = await apiFetch("/mfi/analytics/segments");
  renderSimpleTable(els.segmentAnalytics, rows, [
    ["segment_feature", "Segment"],
    ["segment_value", "Value"],
    ["n", "N"],
    ["avg_high_risk_probability", "Avg risk", formatPercent],
    ["high_risk_share", "High-risk share", formatPercent],
  ]);
}

async function refreshPolicyAnalytics() {
  const payload = await apiFetch("/mfi/analytics/policies");
  state.policyAnalytics = payload;
  renderPolicyAnalytics(payload);
}

async function refreshDecisionAnalytics() {
  const payload = await apiFetch("/mfi/analytics/decisions");
  state.decisionAnalytics = payload;
  renderPortfolioOverview();
  renderDecisionAudit(payload);
}

function renderPolicyAnalytics(payload) {
  els.policyNote.textContent = payload.note || "";
  renderPortfolioOverview();

  if (!payload.scored_application_count) {
    els.policyAnalytics.className = "policy-grid empty";
    els.policyAnalytics.textContent = "Score applications to compare policies.";
    els.policySegments.className = "table-shell empty";
    els.policySegments.textContent = "No segment policy analytics loaded.";
    return;
  }

  els.policyAnalytics.className = "policy-grid";
  els.policyAnalytics.innerHTML = (payload.policies || [])
    .map(renderPolicyCard)
    .join("");

  renderSimpleTable(els.policySegments, payload.segments || [], [
    ["policy", "Policy", formatPolicyName],
    ["segment_feature", "Segment"],
    ["segment_value", "Value"],
    ["n", "N"],
    ["auto_approval_rate", "Approve", formatPercent],
    ["manual_review_rate", "Review", formatPercent],
    ["auto_decline_rate", "Decline", formatPercent],
    ["mean_high_risk_probability", "Avg risk", formatPercent],
    ["predicted_high_risk_share", "High-risk share", formatPercent],
  ]);
}

function renderDecisionAudit(payload) {
  if (!payload?.decided_application_count) {
    els.decisionAudit.className = "table-shell empty";
    els.decisionAudit.textContent = "No analyst decisions recorded yet.";
    return;
  }

  const rows = decisionAuditRows(payload);
  renderSimpleTable(els.decisionAudit, rows, [
    ["view", "View"],
    ["segment", "Segment"],
    ["decision", "Decision", formatPolicyName],
    ["count", "Count"],
    ["share", "Share", formatPercent],
    ["avg_risk", "Avg risk", formatPercent],
    ["avg_proxy_delta", "Proxy delta", formatPercent],
  ]);
}

function decisionAuditRows(payload) {
  const rows = [];
  (payload.risk_rows || []).forEach((row) => {
    rows.push({
      view: "Risk band",
      segment: formatPolicyName(row.risk_band),
      decision: row.decision,
      count: row.count,
      share: row.rate_within_risk_band,
      avg_risk: row.mean_high_risk_probability,
      avg_proxy_delta: null,
    });
  });
  (payload.proxy_rows || []).forEach((row) => {
    rows.push({
      view: "Proxy signal",
      segment: formatPolicyName(row.proxy_sensitivity_bucket),
      decision: row.decision,
      count: row.count,
      share: row.rate_within_bucket,
      avg_risk: row.mean_high_risk_probability,
      avg_proxy_delta: row.mean_proxy_sensitivity_delta,
    });
  });
  (payload.recommendation_rows || []).forEach((row) => {
    rows.push({
      view: "Recommendation",
      segment: row.recommendation_title || formatPolicyName(row.recommendation_code),
      decision: row.decision,
      count: row.count,
      share: row.rate_within_recommendation,
      avg_risk: row.mean_high_risk_probability,
      avg_proxy_delta: null,
    });
  });
  (payload.district_rows || []).forEach((row) => {
    rows.push({
      view: "District",
      segment: row.district,
      decision: row.decision,
      count: row.count,
      share: row.rate_within_district,
      avg_risk: row.mean_high_risk_probability,
      avg_proxy_delta: null,
    });
  });
  return rows;
}

function renderPolicyCard(policy) {
  const approve = Math.max(0, Number(policy.auto_approval_rate || 0) * 100);
  const review = Math.max(0, Number(policy.manual_review_rate || 0) * 100);
  const decline = Math.max(0, Number(policy.auto_decline_rate || 0) * 100);
  const approveWidth = approve ? `${approve}%` : "0";
  const reviewWidth = review ? `${review}%` : "0";
  const declineWidth = decline ? `${decline}%` : "0";

  return `
    <article class="policy-card">
      <div class="policy-card-heading">
        <div>
          <span>Policy</span>
          <strong>${escapeHtml(formatPolicyName(policy.policy))}</strong>
        </div>
        <em>${formatPercent(policy.mean_high_risk_probability)}</em>
      </div>
      <div class="policy-mix" aria-label="Policy action mix">
        <span class="policy-approve" style="width: ${approveWidth}"></span>
        <span class="policy-review" style="width: ${reviewWidth}"></span>
        <span class="policy-decline" style="width: ${declineWidth}"></span>
      </div>
      <div class="policy-card-metrics">
        <div><span>Approve</span><strong>${formatPercent(policy.auto_approval_rate)}</strong></div>
        <div><span>Review</span><strong>${formatPercent(policy.manual_review_rate)}</strong></div>
        <div><span>Decline</span><strong>${formatPercent(policy.auto_decline_rate)}</strong></div>
      </div>
      <div class="policy-thresholds">
        <span>Approve <= ${formatPercent(policy.approve_threshold)}</span>
        <span>Decline >= ${formatPercent(policy.decline_threshold)}</span>
      </div>
    </article>
  `;
}

async function refreshAudit() {
  const rows = await apiFetch("/admin/audit-events");
  renderSimpleTable(els.auditTrail, rows, [
    ["created_at", "Time"],
    ["actor_email", "Actor"],
    ["action", "Action"],
    ["entity_type", "Entity"],
    ["entity_id", "ID"],
  ]);
}

async function clearApplications() {
  const confirmed = window.confirm("Clear all loan applications from the local demo database?");
  if (!confirmed) return;

  const result = await apiFetch("/admin/applications", {
    method: "DELETE",
  });

  resetApplicationViews();
  showMessage(`Cleared ${result.deleted_count} applications`, "ok");
  await refreshAudit();
}

function renderSimpleTable(container, rows, columns) {
  if (!rows.length) {
    container.className = "table-shell empty";
    container.textContent = "No records loaded.";
    return;
  }
  container.className = "table-shell";
  const head = columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map(([key, _label, formatter]) => {
          const value = formatter ? formatter(row[key]) : row[key];
          return `<td>${escapeHtml(value ?? "-")}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function wireEvents() {
  els.apiBase.value = state.apiBase;
  els.checkApiButton.addEventListener("click", () => checkApi());
  els.apiBase.addEventListener("change", () => checkApi());
  els.roleTabs.forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
  els.authForm.addEventListener("submit", (event) => {
    event.preventDefault();
    authenticate("login").catch((error) => showMessage(error.message, "error"));
  });
  els.registerButton.addEventListener("click", () => {
    authenticate("register").catch((error) => showMessage(error.message, "error"));
  });
  els.logoutButton.addEventListener("click", () => {
    clearSession();
    showMessage("Signed out", "info");
  });
  els.demoButtons.forEach((button) => {
    button.addEventListener("click", () => fillDemoCredentials(button.dataset.demo, button.dataset.role));
  });
  els.fillDemoApplication.addEventListener("click", () => fillApplicationForm(demoApplication));
  els.applicationForm.addEventListener("submit", (event) => {
    submitApplication(event).catch((error) => showMessage(error.message, "error"));
  });
  els.loadBorrowerApplication.addEventListener("click", () => {
    loadBorrowerApplication().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshBorrowerApplication.addEventListener("click", () => {
    loadBorrowerApplication().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshApplications.addEventListener("click", () => {
    refreshApplications().catch((error) => showMessage(error.message, "error"));
  });
  els.scoreSelectedApplication.addEventListener("click", () => {
    scoreSelectedApplication().catch((error) => showMessage(error.message, "error"));
  });
  els.decisionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveApplicationDecision().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshAnalytics.addEventListener("click", () => {
    refreshAnalytics().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshPolicyAnalytics.addEventListener("click", () => {
    refreshPolicyAnalytics().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshAudit.addEventListener("click", () => {
    refreshAudit().catch((error) => showMessage(error.message, "error"));
  });
  els.clearApplications.addEventListener("click", () => {
    clearApplications().catch((error) => showMessage(error.message, "error"));
  });
}

function restoreState() {
  updateSessionStrip();
  fillApplicationForm(demoApplication);
  const lastApplicationId = localStorage.getItem("microscore.lastApplicationId");
  if (lastApplicationId) els.borrowerApplicationId.value = lastApplicationId;
}

wireEvents();
restoreState();
checkApi();
