const state = {
  apiBase: localStorage.getItem("microscore.apiBase") || "http://127.0.0.1:8000",
  token: localStorage.getItem("microscore.token") || "",
  role: localStorage.getItem("microscore.role") || "",
  email: localStorage.getItem("microscore.email") || "",
  selectedApplicationId: "",
  applications: [],
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
  refreshApplications: document.querySelector("#refreshApplications"),
  applicationsTable: document.querySelector("#applicationsTable"),
  scoreSelectedApplication: document.querySelector("#scoreSelectedApplication"),
  scoreDetail: document.querySelector("#scoreDetail"),
  refreshAnalytics: document.querySelector("#refreshAnalytics"),
  segmentAnalytics: document.querySelector("#segmentAnalytics"),
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

  els.borrowerApplicationId.value = "";
  els.borrowerApplicationCard.className = "result-block empty";
  els.borrowerApplicationCard.textContent = "No application selected.";

  els.applicationsTable.className = "table-shell empty";
  els.applicationsTable.textContent = "No applications loaded.";

  els.scoreDetail.className = "result-block empty";
  els.scoreDetail.textContent = "Select an application.";

  els.segmentAnalytics.className = "table-shell empty";
  els.segmentAnalytics.textContent = "No segment analytics loaded.";
}

function renderApplication(application) {
  const score = application.score_result;
  const riskClass = score ? `risk-${score.risk_band}` : "";
  return `
    <div class="metric-grid">
      <div class="metric"><span>Status</span><strong>${escapeHtml(application.status)}</strong></div>
      <div class="metric"><span>Amount</span><strong>${formatMoney(application.requested_amount)}</strong></div>
      <div class="metric"><span>District</span><strong>${escapeHtml(application.district || "-")}</strong></div>
      <div class="metric"><span>Risk</span><strong class="${riskClass}">${score ? escapeHtml(score.risk_band) : "not scored"}</strong></div>
    </div>
    <p class="record-line"><strong>ID:</strong> ${escapeHtml(application.id)}</p>
    ${score ? renderScore(score) : ""}
  `;
}

function renderScore(score) {
  const factors = (score.top_model_factors || [])
    .slice(0, 5)
    .map((factor) => `<li>${escapeHtml(factor.feature)} - ${Number(factor.abs_value).toFixed(3)}</li>`)
    .join("");
  const warnings = (score.warnings || [])
    .map((warning) => `<li>${escapeHtml(warning)}</li>`)
    .join("");
  const scenarios = renderScenarioScores(score);
  const decisionSupport = renderDecisionSupport(score.decision_support);
  return `
    <div class="metric-grid">
      <div class="metric"><span>Probability</span><strong>${formatPercent(score.high_risk_probability)}</strong></div>
      <div class="metric"><span>Model</span><strong>${escapeHtml(score.model_version)}</strong></div>
      <div class="metric"><span>Proxy sensitivity</span><strong>${formatPercent(score.proxy_sensitivity_delta)}</strong></div>
    </div>
    ${decisionSupport}
    ${scenarios}
    <ul class="factor-list">${factors}</ul>
    <ul class="warning-list">${warnings}</ul>
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
        </tr>
      `,
    )
    .join("");
  els.applicationsTable.innerHTML = `
    <table>
      <thead><tr><th>Status</th><th>Borrower</th><th>Amount</th><th>District</th><th>Risk</th></tr></thead>
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

async function refreshApplications() {
  state.applications = await apiFetch("/mfi/applications");
  if (!state.selectedApplicationId && state.applications.length) {
    state.selectedApplicationId = state.applications[0].id;
  }
  renderApplicationsTable(state.applications);
  if (state.selectedApplicationId) selectApplication(state.selectedApplicationId);
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
  showMessage("Application scored", "ok");
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
  els.refreshAnalytics.addEventListener("click", () => {
    refreshAnalytics().catch((error) => showMessage(error.message, "error"));
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
