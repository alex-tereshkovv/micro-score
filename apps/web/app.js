const DEFAULT_API_BASE = "http://127.0.0.1:8010";
const API_BASE_CANDIDATES = [
  "http://127.0.0.1:8010",
  "http://127.0.0.1:8011",
  "http://127.0.0.1:8012",
  "http://127.0.0.1:8000",
];
const queryParams = new URLSearchParams(window.location.search);
const queryApiBase = queryParams.get("api");
const queryDemoMode = queryParams.get("demo");
const forceStaticDemo = queryDemoMode === "static";
const LOCAL_HOSTNAMES = new Set(["", "localhost", "127.0.0.1", "0.0.0.0", "::1"]);
const hostedStaticPage = !LOCAL_HOSTNAMES.has(window.location.hostname);
// A 15-point proxy swing is enough to make an analyst slow down. Real pilot data should get the final vote here.
const HIGH_PROXY_SENSITIVITY_DELTA = 0.15;
const DEMO_CONSENT_VERSION = "synthetic-demo-v1";

function normalizeApiBase(value) {
  return String(value || "").trim().replace(/\/$/, "");
}

const state = {
  apiBase: normalizeApiBase(
    queryApiBase || localStorage.getItem("microscore.apiBase") || DEFAULT_API_BASE,
  ),
  token: localStorage.getItem("microscore.token") || "",
  role: localStorage.getItem("microscore.role") || "",
  email: localStorage.getItem("microscore.email") || "",
  demoMode: forceStaticDemo || hostedStaticPage || localStorage.getItem("microscore.demoMode") === "static",
  selectedApplicationId: "",
  applications: [],
  policyAnalytics: null,
  decisionAnalytics: null,
  organizations: [],
};

const els = {
  authScreen: document.querySelector("#authScreen"),
  appShell: document.querySelector("#appShell"),
  apiBase: document.querySelector("#apiBase"),
  apiStatus: document.querySelector("#apiStatus"),
  connectionTitle: document.querySelector("#connection-title"),
  apiSettings: document.querySelector(".api-settings"),
  checkApiButton: document.querySelector("#checkApiButton"),
  roleTabs: document.querySelectorAll(".role-tab"),
  views: document.querySelectorAll(".view-grid"),
  viewTitle: document.querySelector("#viewTitle"),
  workspaceRoleLabel: document.querySelector("#workspaceRoleLabel"),
  authForm: document.querySelector("#authForm"),
  registerButton: document.querySelector("#registerButton"),
  email: document.querySelector("#email"),
  password: document.querySelector("#password"),
  demoModePill: document.querySelector("#demoModePill"),
  resetDemoData: document.querySelector("#resetDemoData"),
  sessionRole: document.querySelector("#sessionRole"),
  logoutButton: document.querySelector("#logoutButton"),
  messageArea: document.querySelector("#messageArea"),
  demoButtons: document.querySelectorAll("[data-demo]"),
  applicationForm: document.querySelector("#applicationForm"),
  fillDemoApplication: document.querySelector("#fillDemoApplication"),
  borrowerConsent: document.querySelector("#borrowerConsent"),
  borrowerApplicationId: document.querySelector("#borrowerApplicationId"),
  loadBorrowerApplication: document.querySelector("#loadBorrowerApplication"),
  refreshBorrowerApplication: document.querySelector("#refreshBorrowerApplication"),
  borrowerApplicationCard: document.querySelector("#borrowerApplicationCard"),
  portfolioOverview: document.querySelector("#portfolioOverview"),
  refreshApplications: document.querySelector("#refreshApplications"),
  exportApplications: document.querySelector("#exportApplications"),
  applicationsTable: document.querySelector("#applicationsTable"),
  scoreSelectedApplication: document.querySelector("#scoreSelectedApplication"),
  loadReviewPacket: document.querySelector("#loadReviewPacket"),
  scoreDetail: document.querySelector("#scoreDetail"),
  reviewPacket: document.querySelector("#reviewPacket"),
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
  staffForm: document.querySelector("#staffForm"),
  staffUsers: document.querySelector("#staffUsers"),
  refreshUsers: document.querySelector("#refreshUsers"),
  applicationOrganization: document.querySelector("#applicationOrganization"),
  staffOrganization: document.querySelector("#staffOrganization"),
  organizationForm: document.querySelector("#organizationForm"),
  organizationDirectory: document.querySelector("#organizationDirectory"),
  refreshOrganizations: document.querySelector("#refreshOrganizations"),
  clearApplications: document.querySelector("#clearApplications"),
};

const viewTitles = {
  borrowerView: "Borrower workspace",
  mfiView: "MFI analyst workspace",
  adminView: "Admin workspace",
};

const roleDefaultViews = {
  borrower: "borrowerView",
  mfi_analyst: "mfiView",
  admin: "adminView",
};

const roleLabels = {
  borrower: "Borrower portal",
  mfi_analyst: "MFI analyst console",
  admin: "Admin console",
};

const roleAllowedViews = {
  borrower: ["borrowerView"],
  mfi_analyst: ["mfiView"],
  admin: ["adminView", "mfiView"],
};

const routeToView = {
  "#/borrower": "borrowerView",
  "#/mfi": "mfiView",
  "#/admin": "adminView",
};

const viewToRoute = {
  borrowerView: "#/borrower",
  mfiView: "#/mfi",
  adminView: "#/admin",
};

const roleDefaultRoutes = {
  borrower: "#/borrower",
  mfi_analyst: "#/mfi",
  admin: "#/admin",
};

const demoApplication = {
  organization_id: "pavlodar-demo-mfi",
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
  if (state.demoMode) {
    localStorage.setItem("microscore.demoMode", "static");
  } else {
    localStorage.removeItem("microscore.demoMode");
  }
}

function clearSession() {
  state.token = "";
  state.role = "";
  state.email = "";
  saveSession();
  updateSessionStrip();
  navigateToRoute("#/login");
}

async function logoutSession() {
  try {
    if (state.token) {
      await apiFetch("/auth/logout", { method: "POST" });
    }
  } catch (_error) {
    // An expired token is already logged out from the server's point of view.
  } finally {
    clearSession();
    showMessage("Signed out", "info");
  }
}

function updateSessionStrip() {
  els.demoModePill.hidden = !state.demoMode;
  els.resetDemoData.hidden = !state.demoMode;
  syncConnectionPanel();
  if (state.token) {
    els.sessionRole.textContent = `${state.role} - ${state.email}`;
    els.sessionRole.classList.remove("muted");
    els.workspaceRoleLabel.textContent = roleLabels[state.role] || "Personal workspace";
  } else {
    els.sessionRole.textContent = "No session";
    els.sessionRole.classList.add("muted");
    els.workspaceRoleLabel.textContent = "Personal workspace";
  }
}

function syncConnectionPanel() {
  const demoMode = Boolean(state.demoMode);
  els.connectionTitle.textContent = demoMode ? "Demo system" : "Local system";
  els.apiSettings.hidden = demoMode;
  els.checkApiButton.title = demoMode ? "Check demo system" : "Check API";
  // Public demos should feel like a product, not like we accidentally left the localhost plumbing on the table.
  els.checkApiButton.setAttribute("aria-label", els.checkApiButton.title);
}

function currentAllowedViews() {
  return roleAllowedViews[state.role] || [];
}

function configureRoleNavigation() {
  const allowedViews = currentAllowedViews();
  els.roleTabs.forEach((tab) => {
    const roles = String(tab.dataset.roles || "")
      .split(/\s+/)
      .filter(Boolean);
    tab.hidden = !roles.includes(state.role);
  });
  els.views.forEach((view) => {
    view.hidden = !allowedViews.includes(view.id);
  });
}

function currentRoute() {
  return window.location.hash || "#/login";
}

function routeForRole(role) {
  return roleDefaultRoutes[role] || "#/borrower";
}

function viewForRoute(route) {
  return routeToView[route] || null;
}

function routeUrl(route) {
  return `${window.location.pathname}${window.location.search}${route}`;
}

function replaceRoute(route) {
  window.history.replaceState(null, "", routeUrl(route));
}

function navigateToRoute(route) {
  if (window.location.hash === route) {
    applyRoute();
    return;
  }
  window.location.hash = route;
}

function navigateToRole(role) {
  navigateToRoute(routeForRole(role));
}

function navigateToView(viewId) {
  const route = viewToRoute[viewId];
  if (route) navigateToRoute(route);
}

function applyRoute() {
  const signedIn = Boolean(state.token);

  if (!signedIn) {
    if (window.location.hash !== "#/login") replaceRoute("#/login");
    setAppMode();
    return;
  }

  configureRoleNavigation();
  const allowedViews = currentAllowedViews();
  const fallbackView = roleDefaultViews[state.role] || allowedViews[0] || "borrowerView";
  const requestedView = viewForRoute(currentRoute());
  const targetView = requestedView && allowedViews.includes(requestedView)
    ? requestedView
    : fallbackView;
  const targetRoute = viewToRoute[targetView];

  if (targetRoute && currentRoute() !== targetRoute) {
    replaceRoute(targetRoute);
  }

  setAppMode(targetView);
}

function setAppMode(targetView = null) {
  const signedIn = Boolean(state.token);
  document.body.classList.toggle("logged-in", signedIn);
  document.body.classList.toggle("logged-out", !signedIn);
  updateSessionStrip();

  if (signedIn) {
    configureRoleNavigation();
    switchView(targetView || roleDefaultViews[state.role] || currentAllowedViews()[0] || "borrowerView", {
      updateRoute: false,
    });
    showAppPage();
  } else {
    showAuthPage();
  }
}

function showAppPage() {
  const shouldAnimate = els.appShell.hidden;
  els.appShell.hidden = false;
  if (shouldAnimate) {
    els.appShell.classList.add("page-enter");
    if (!els.authScreen.hidden) {
      els.authScreen.classList.add("page-exit");
    }
    window.scrollTo(0, 0);
    window.setTimeout(() => {
      els.authScreen.hidden = true;
      els.authScreen.classList.remove("page-exit");
      els.appShell.classList.remove("page-enter");
    }, 280);
  } else {
    els.authScreen.hidden = true;
  }
}

function showAuthPage() {
  const shouldAnimate = !els.appShell.hidden;
  els.authScreen.hidden = false;
  if (shouldAnimate) {
    els.authScreen.classList.add("page-enter");
    els.appShell.classList.add("page-exit");
    window.scrollTo(0, 0);
    window.setTimeout(() => {
      els.appShell.hidden = true;
      els.appShell.classList.remove("page-exit");
      els.authScreen.classList.remove("page-enter");
    }, 280);
  } else {
    els.appShell.hidden = true;
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
  if (state.demoMode && hasStaticDemoApi()) {
    return staticDemoFetch(path, options);
  }

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  let response;
  try {
    response = await fetch(`${state.apiBase}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    if (hasStaticDemoApi()) {
      activateStaticDemo("Static demo mode - API offline");
      return staticDemoFetch(path, options);
    }
    throw error;
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    throw new Error(formatApiError(detail));
  }
  return data;
}

function formatApiError(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || String(item)).join("; ");
  }
  if (detail && typeof detail === "object") {
    const extras = detail.requirements || detail.forbidden_fields || [];
    return [detail.message, ...extras].filter(Boolean).join(": ");
  }
  return "Request failed";
}

async function apiBlob(path) {
  if (state.demoMode && hasStaticDemoApi()) {
    return window.MicroScoreMockApi.blob(path, { token: state.token, role: state.role, email: state.email });
  }

  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let response;
  try {
    response = await fetch(`${state.apiBase}${path}`, { headers });
  } catch (error) {
    if (hasStaticDemoApi()) {
      activateStaticDemo("Static demo mode - API offline");
      return window.MicroScoreMockApi.blob(path, { token: state.token, role: state.role, email: state.email });
    }
    throw error;
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.blob();
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function hasStaticDemoApi() {
  return Boolean(window.MicroScoreMockApi);
}

function staticDemoFetch(path, options = {}) {
  return window.MicroScoreMockApi.request(path, options, {
    token: state.token,
    role: state.role,
    email: state.email,
  });
}

function activateStaticDemo(statusText = "Static demo mode - synthetic data only") {
  if (!hasStaticDemoApi()) return false;
  state.demoMode = true;
  saveSession();
  syncConnectionPanel();
  els.apiStatus.textContent = statusText;
  els.apiStatus.className = "status-line neutral";
  return true;
}

async function checkApi() {
  if (forceStaticDemo && activateStaticDemo()) {
    return true;
  }

  const requestedBase = normalizeApiBase(els.apiBase.value) || state.apiBase || DEFAULT_API_BASE;
  const candidates = Array.from(new Set([requestedBase, ...API_BASE_CANDIDATES]));
  els.apiStatus.textContent = "Checking API...";
  els.apiStatus.className = "status-line neutral";

  for (const base of candidates) {
    try {
      const health = await fetchHealth(base);
      state.demoMode = false;
      state.apiBase = base;
      els.apiBase.value = base;
      saveSession();
      syncConnectionPanel();
      els.apiStatus.textContent = `${health.status} - ${health.service}`;
      els.apiStatus.className = "status-line ok";
      return true;
    } catch (_error) {
      // Try the next local development port.
    }
  }

  state.apiBase = requestedBase;
  els.apiBase.value = requestedBase;
  saveSession();
  if (activateStaticDemo("Static demo mode - API offline")) {
    return true;
  }
  els.apiStatus.textContent = "Offline - start MicroScore and retry";
  els.apiStatus.className = "status-line error";
  return false;
}

async function checkApiAndOrganizations() {
  const online = await checkApi();
  if (online) await refreshOrganizations();
  return online;
}

async function fetchHealth(apiBase) {
  const response = await fetch(`${apiBase}/health`);
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.detail || response.statusText);
  return data;
}

function switchView(viewId, options = {}) {
  const { updateRoute = true } = options;
  const allowedViews = currentAllowedViews();
  const targetView = allowedViews.includes(viewId) ? viewId : allowedViews[0] || viewId;
  els.views.forEach((view) => view.classList.toggle("active-view", view.id === targetView));
  els.roleTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.view === targetView));
  els.viewTitle.textContent = viewTitles[targetView] || "Workspace";
  if (updateRoute) navigateToView(targetView);
}

async function authenticate(mode) {
  const payload = {
    email: els.email.value.trim(),
    password: els.password.value,
  };
  if (mode === "register") payload.role = "borrower";

  const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
  const auth = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.token = auth.access_token;
  state.role = auth.role;
  state.email = payload.email;
  saveSession();
  navigateToRole(auth.role);
  showMessage(`Signed in as ${auth.role}`, "ok");
  return auth;
}

function fillDemoCredentials(email) {
  els.email.value = email;
  els.password.value = "password123";
}

async function enterDemoWorkspace(email, role) {
  fillDemoCredentials(email);
  const online = await checkApiAndOrganizations();
  if (!online) {
    showMessage("Start MicroScore first, then try demo entry again", "error");
    return;
  }
  await authenticate("login");
  await loadRoleWorkspace(role);
}

async function loadRoleWorkspace(role) {
  if (role === "mfi_analyst") {
    await refreshApplications();
  } else if (role === "admin") {
    await Promise.all([refreshAudit(), refreshStaffUsers(), refreshOrganizations()]);
  }
}

async function resetStaticDemoData() {
  if (!state.demoMode || !window.MicroScoreMockApi) return;

  window.MicroScoreMockApi.resetDemo();
  resetApplicationViews();
  await refreshOrganizations();
  fillApplicationForm(demoApplication);

  if (state.token) {
    await loadRoleWorkspace(state.role);
  }

  showMessage("Static demo data reset", "ok");
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

function borrowerConsentAcknowledged() {
  return Boolean(els.borrowerConsent?.checked);
}

function applicationPayload() {
  const form = els.applicationForm;
  return {
    requested_amount: formNumber(form, "requested_amount"),
    organization_id: form.elements.organization_id.value,
    purpose: form.elements.purpose.value.trim(),
    district: form.elements.district.value,
    settlement_type: form.elements.settlement_type.value,
    consent_confirmed: borrowerConsentAcknowledged(),
    consent_version: DEMO_CONSENT_VERSION,
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

function renderStateBlock(type, title, body) {
  const spinner = type === "loading" ? "<span class=\"state-spinner\" aria-hidden=\"true\"></span>" : "";
  return `
    <div class="state-block state-${escapeHtml(type)}" role="status">
      ${spinner}
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(body)}</span>
    </div>
  `;
}

function setPanelState(container, baseClass, type, title, body) {
  const emptyClass = type === "empty" ? " empty" : "";
  container.className = `${baseClass}${emptyClass} state-host state-host-${type}`;
  container.innerHTML = renderStateBlock(type, title, body);
}

async function withButtonBusy(button, busyText, task) {
  if (!button) return task();

  const readyText = button.textContent;
  button.disabled = true;
  button.classList.add("is-busy");
  if (busyText) button.textContent = busyText;

  try {
    return await task();
  } finally {
    button.disabled = false;
    button.classList.remove("is-busy");
    button.textContent = readyText;
  }
}

function resetApplicationViews() {
  localStorage.removeItem("microscore.lastApplicationId");
  state.selectedApplicationId = "";
  state.applications = [];
  state.policyAnalytics = null;
  state.decisionAnalytics = null;

  els.borrowerApplicationId.value = "";
  els.borrowerConsent.checked = false;
  setPanelState(
    els.borrowerApplicationCard,
    "result-block",
    "empty",
    "No application selected",
    "Submit or load an application to view its status.",
  );

  setPanelState(
    els.applicationsTable,
    "table-shell",
    "empty",
    "No applications loaded",
    "Refresh the queue or submit a borrower demo application.",
  );

  setPanelState(
    els.scoreDetail,
    "result-block",
    "empty",
    "Select an application",
    "Choose a queue row to inspect score detail and timeline.",
  );
  setPanelState(
    els.reviewPacket,
    "result-block",
    "empty",
    "Open a review packet",
    "Score an application, then open its governance packet.",
  );
  els.decisionForm.reset();

  setPanelState(
    els.portfolioOverview,
    "portfolio-overview",
    "empty",
    "Portfolio not loaded",
    "Load applications to view risk, district, policy, and decision analytics.",
  );

  setPanelState(
    els.segmentAnalytics,
    "table-shell",
    "empty",
    "No segment analytics loaded",
    "Refresh analytics after applications are scored.",
  );

  els.policyNote.textContent = "Score applications to compare policies.";
  setPanelState(
    els.policyAnalytics,
    "policy-grid",
    "empty",
    "No policy analytics loaded",
    "Score applications to compare approval strategies.",
  );
  setPanelState(
    els.policySegments,
    "table-shell",
    "empty",
    "No segment policy analytics loaded",
    "Policy segments appear after scoring.",
  );
  setPanelState(
    els.decisionAudit,
    "table-shell",
    "empty",
    "No decision audit loaded",
    "Recorded analyst decisions will appear here.",
  );
}

function renderApplication(application) {
  const score = application.score_result;
  const riskClass = score ? `risk-${score.risk_band}` : "";
  const decision = renderRecordedDecision(application.decision_result);
  const timeline = renderApplicationTimeline(application.timeline_events);
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
    ${timeline}
  `;
}

function renderApplicationTimeline(events) {
  if (!events?.length) return "";

  const rows = events
    .map(
      (event) => `
        <li>
          <div>
            <strong>${escapeHtml(event.title || formatPolicyName(event.action))}</strong>
            <span>${escapeHtml(event.actor_email || "system")}</span>
          </div>
          <em>${escapeHtml(event.created_at)}</em>
          ${renderTimelineDetails(event.details)}
        </li>
      `,
    )
    .join("");
  return `
    <div class="timeline-block">
      <h4>Application timeline</h4>
      <ol>${rows}</ol>
    </div>
  `;
}

function renderTimelineDetails(details) {
  const entries = Object.entries(details || {});
  if (!entries.length) return "";
  const text = entries
    .map(([key, value]) => `${formatPolicyName(key)}: ${formatTimelineValue(value)}`)
    .join(" · ");
  return `<p>${escapeHtml(text)}</p>`;
}

function formatTimelineValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return formatMoney(value);
  return formatPolicyName(value);
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
  const modelUseNotice = renderModelUseNotice(score);
  const decisionSupport = renderDecisionSupport(score.decision_support);
  const explanation = renderLocalExplanation(score.explanation, score.top_model_factors);
  return `
    <div class="metric-grid">
      <div class="metric"><span>Probability</span><strong>${formatPercent(score.high_risk_probability)}</strong></div>
      <div class="metric"><span>Model</span><strong>${escapeHtml(score.model_version)}</strong></div>
      <div class="metric"><span>Proxy sensitivity</span><strong>${formatPercent(score.proxy_sensitivity_delta)}</strong></div>
    </div>
    ${modelUseNotice}
    ${decisionSupport}
    ${scenarios}
    ${explanation}
    <ul class="warning-list">${warnings}</ul>
  `;
}

function renderModelUseNotice(model) {
  if (!model) {
    return `
      <aside class="model-use-notice notice-neutral" aria-label="Model use notice">
        <strong>Not scored yet</strong>
        <span>Score the application before using the review packet for a decision.</span>
      </aside>
    `;
  }

  const proxyDelta = Number(model.proxy_sensitivity_delta || 0);
  const highProxySensitivity = proxyDelta >= HIGH_PROXY_SENSITIVITY_DELTA;
  const noticeClass = highProxySensitivity ? "notice-caution" : "notice-neutral";
  const title = highProxySensitivity ? "Manual review required" : "Decision-support only";
  const body = highProxySensitivity
    ? `Proxy sensitivity is ${formatPercent(proxyDelta)}. Treat this as a research signal and verify affordability, income stability, and borrower context before any action.`
    : "Use this score as one input in a human review; the demo is synthetic and not validated for real lending decisions.";

  // Keep this warning in the product surface, not only in docs. Future us may forget; auditors have annoyingly good memories.
  return `
    <aside class="model-use-notice ${noticeClass}" aria-label="Model use notice">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(body)}</span>
    </aside>
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
  if (!borrowerConsentAcknowledged()) {
    showMessage("Confirm demo data consent before submitting", "error");
    els.borrowerConsent.focus();
    return;
  }
  const application = await apiFetch("/applications", {
    method: "POST",
    body: JSON.stringify(applicationPayload()),
  });
  rememberApplication(application.id);
  const applicationWithTimeline = await attachApplicationTimeline(application);
  els.borrowerApplicationCard.classList.remove("empty");
  els.borrowerApplicationCard.innerHTML = renderApplication(applicationWithTimeline);
  showMessage("Application submitted", "ok");
}

async function loadBorrowerApplication() {
  const id = els.borrowerApplicationId.value.trim();
  if (!id) {
    showMessage("Enter an application ID", "error");
    return;
  }
  const application = await apiFetch(`/applications/${encodeURIComponent(id)}`);
  const applicationWithTimeline = await attachApplicationTimeline(application);
  els.borrowerApplicationCard.classList.remove("empty");
  els.borrowerApplicationCard.innerHTML = renderApplication(applicationWithTimeline);
}

async function attachApplicationTimeline(application) {
  const timeline = await apiFetch(`/applications/${encodeURIComponent(application.id)}/timeline`);
  return { ...application, timeline_events: timeline };
}

function renderApplicationsTable(applications) {
  if (!applications.length) {
    setPanelState(
      els.applicationsTable,
      "table-shell",
      "empty",
      "No applications loaded",
      "Submit a borrower demo application or reset static demo data.",
    );
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
  if (application) {
    els.scoreDetail.className = "result-block";
    els.scoreDetail.innerHTML = renderApplication(application);
  } else {
    setPanelState(
      els.scoreDetail,
      "result-block",
      "empty",
      "Select an application",
      "Choose a queue row to inspect score detail and timeline.",
    );
  }
  setPanelState(
    els.reviewPacket,
    "result-block",
    "empty",
    "Open a review packet",
    "Score an application, then open its governance packet.",
  );
  if (application) {
    loadSelectedApplicationTimeline(application.id).catch((error) =>
      showMessage(error.message, "error"),
    );
  }
}

async function loadSelectedApplicationTimeline(applicationId) {
  const timeline = await apiFetch(`/applications/${encodeURIComponent(applicationId)}/timeline`);
  state.applications = state.applications.map((item) =>
    item.id === applicationId ? { ...item, timeline_events: timeline } : item,
  );
  if (state.selectedApplicationId !== applicationId) return;
  const application = state.applications.find((item) => item.id === applicationId);
  if (application) {
    els.scoreDetail.className = "result-block";
    els.scoreDetail.innerHTML = renderApplication(application);
  }
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
    setPanelState(
      els.portfolioOverview,
      "portfolio-overview",
      "empty",
      "Portfolio not loaded",
      "Load applications to view risk, district, policy, and decision analytics.",
    );
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
  return withButtonBusy(els.refreshApplications, "", async () => {
    setPanelState(
      els.applicationsTable,
      "table-shell",
      "loading",
      "Loading application queue",
      "Fetching the latest borrower applications.",
    );
    setPanelState(
      els.portfolioOverview,
      "portfolio-overview",
      "loading",
      "Refreshing portfolio",
      "Updating risk, district, policy, and decision summaries.",
    );

    try {
      state.applications = await apiFetch("/mfi/applications");
    } catch (error) {
      setPanelState(
        els.applicationsTable,
        "table-shell",
        "error",
        "Queue unavailable",
        error.message || "The application queue could not be loaded.",
      );
      setPanelState(
        els.portfolioOverview,
        "portfolio-overview",
        "error",
        "Portfolio unavailable",
        "Analytics will appear after the queue loads successfully.",
      );
      throw error;
    }

    if (!state.selectedApplicationId && state.applications.length) {
      state.selectedApplicationId = state.applications[0].id;
    }
    renderApplicationsTable(state.applications);
    if (state.selectedApplicationId) selectApplication(state.selectedApplicationId);
    renderPortfolioOverview();

    const analyticsResults = await Promise.allSettled([
      refreshAnalytics(),
      refreshPolicyAnalytics(),
      refreshDecisionAnalytics(),
    ]);
    const failedAnalytics = analyticsResults.find((result) => result.status === "rejected");
    if (failedAnalytics) {
      showMessage(failedAnalytics.reason?.message || "Some analytics could not be refreshed", "error");
    }
  });
}

async function exportApplicationsCsv() {
  const blob = await apiBlob("/mfi/applications/export.csv");
  downloadBlob(blob, "microscore-applications.csv");
  showMessage("Portfolio CSV exported", "ok");
}

async function scoreSelectedApplication() {
  if (!state.selectedApplicationId) {
    showMessage("Select an application first", "error");
    return;
  }

  await withButtonBusy(els.scoreSelectedApplication, "Scoring...", async () => {
    setPanelState(
      els.scoreDetail,
      "result-block",
      "loading",
      "Scoring application",
      "Running the model and preparing explanations.",
    );
    try {
      const scored = await apiFetch(`/mfi/applications/${encodeURIComponent(state.selectedApplicationId)}/score`, {
        method: "POST",
      });
      state.applications = state.applications.map((item) => (item.id === scored.id ? scored : item));
      selectApplication(scored.id);
      await refreshAnalytics();
      await refreshPolicyAnalytics();
      showMessage("Application scored", "ok");
    } catch (error) {
      setPanelState(
        els.scoreDetail,
        "result-block",
        "error",
        "Scoring failed",
        error.message || "The selected application could not be scored.",
      );
      throw error;
    }
  });
}

async function loadReviewPacket() {
  if (!state.selectedApplicationId) {
    showMessage("Select an application first", "error");
    return;
  }

  await withButtonBusy(els.loadReviewPacket, "Opening...", async () => {
    setPanelState(
      els.reviewPacket,
      "result-block",
      "loading",
      "Opening review packet",
      "Collecting governance flags, factors, and timeline events.",
    );
    try {
      const packet = await apiFetch(
        `/mfi/applications/${encodeURIComponent(state.selectedApplicationId)}/review-packet`,
      );
      els.reviewPacket.className = "result-block";
      els.reviewPacket.innerHTML = renderReviewPacket(packet);
    } catch (error) {
      setPanelState(
        els.reviewPacket,
        "result-block",
        "error",
        "Review packet unavailable",
        error.message || "The review packet could not be opened.",
      );
      throw error;
    }
  });
}

function renderReviewPacket(packet) {
  const model = packet.model_summary;
  const decision = packet.analyst_decision;
  const flags = (packet.governance_flags || [])
    .map((flag) => `<span>${escapeHtml(formatPolicyName(flag))}</span>`)
    .join("");
  const checklist = (packet.checklist || [])
    .map(
      (item) => `
        <li class="checklist-${escapeHtml(item.status)}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(formatPolicyName(item.status))}${item.evidence ? ` · ${escapeHtml(item.evidence)}` : ""}</span>
        </li>
      `,
    )
    .join("");
  const riskFactors = renderPacketFactors(packet.top_risk_factors, "Raises risk");
  const protectiveFactors = renderPacketFactors(packet.top_protective_factors, "Reduces risk");
  const modelUseNotice = renderModelUseNotice(model);
  const timeline = renderApplicationTimeline(packet.timeline_events);

  return `
    <div class="review-packet">
      <div class="packet-heading">
        <div>
          <span>Review packet</span>
          <strong>${escapeHtml(packet.application_id)}</strong>
        </div>
        <em>${escapeHtml(packet.generated_at)}</em>
      </div>
      <div class="metric-grid">
        <div class="metric"><span>Risk</span><strong class="${model ? `risk-${escapeHtml(model.risk_band)}` : ""}">${model ? escapeHtml(model.risk_band) : "not scored"}</strong></div>
        <div class="metric"><span>Probability</span><strong>${model ? formatPercent(model.high_risk_probability) : "-"}</strong></div>
        <div class="metric"><span>Proxy delta</span><strong>${model ? formatPercent(model.proxy_sensitivity_delta) : "-"}</strong></div>
        <div class="metric"><span>Decision</span><strong>${decision ? escapeHtml(formatPolicyName(decision.decision)) : "not recorded"}</strong></div>
      </div>
      ${modelUseNotice}
      <div class="packet-flags">${flags || "<span>No governance flags</span>"}</div>
      <div class="packet-columns">
        <section>
          <h4>Checklist</h4>
          <ul class="packet-checklist">${checklist}</ul>
        </section>
        <section>
          <h4>Factors</h4>
          ${riskFactors}
          ${protectiveFactors}
        </section>
      </div>
      ${timeline}
      <p class="packet-note">${escapeHtml(packet.audit_note)}</p>
    </div>
  `;
}

function renderPacketFactors(factors, title) {
  if (!factors?.length) {
    return `<div class="packet-factor-group"><strong>${escapeHtml(title)}</strong><p class="tiny-text">No factors available.</p></div>`;
  }
  const rows = factors
    .map(
      (factor) => `
        <li>
          <span>${escapeHtml(factor.label || factor.feature)}</span>
          <strong>${Number(factor.value || 0).toFixed(3)}</strong>
        </li>
      `,
    )
    .join("");
  return `
    <div class="packet-factor-group">
      <strong>${escapeHtml(title)}</strong>
      <ul>${rows}</ul>
    </div>
  `;
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
  await loadReviewPacket();
  showMessage("MFI decision saved", "ok");
}

async function refreshAnalytics() {
  setPanelState(
    els.segmentAnalytics,
    "table-shell",
    "loading",
    "Refreshing segment audit",
    "Checking risk by borrower and regional segments.",
  );
  try {
    const rows = await apiFetch("/mfi/analytics/segments");
    renderSimpleTable(els.segmentAnalytics, rows, [
      ["segment_feature", "Segment"],
      ["segment_value", "Value"],
      ["n", "N"],
      ["avg_high_risk_probability", "Avg risk", formatPercent],
      ["high_risk_share", "High-risk share", formatPercent],
    ]);
  } catch (error) {
    setPanelState(
      els.segmentAnalytics,
      "table-shell",
      "error",
      "Segment audit unavailable",
      error.message || "Segment analytics could not be loaded.",
    );
    throw error;
  }
}

async function refreshPolicyAnalytics() {
  els.policyNote.textContent = "Refreshing policy analytics...";
  setPanelState(
    els.policyAnalytics,
    "policy-grid",
    "loading",
    "Refreshing policy lab",
    "Comparing approve, review, and decline strategies.",
  );
  setPanelState(
    els.policySegments,
    "table-shell",
    "loading",
    "Refreshing policy segments",
    "Checking how strategies behave across segments.",
  );
  try {
    const payload = await apiFetch("/mfi/analytics/policies");
    state.policyAnalytics = payload;
    renderPolicyAnalytics(payload);
  } catch (error) {
    els.policyNote.textContent = "Policy analytics unavailable.";
    setPanelState(
      els.policyAnalytics,
      "policy-grid",
      "error",
      "Policy lab unavailable",
      error.message || "Policy analytics could not be loaded.",
    );
    setPanelState(
      els.policySegments,
      "table-shell",
      "error",
      "Policy segments unavailable",
      "Retry after applications are loaded and scored.",
    );
    throw error;
  }
}

async function refreshDecisionAnalytics() {
  setPanelState(
    els.decisionAudit,
    "table-shell",
    "loading",
    "Refreshing decision audit",
    "Comparing analyst decisions with risk bands and proxy signals.",
  );
  try {
    const payload = await apiFetch("/mfi/analytics/decisions");
    state.decisionAnalytics = payload;
    renderPortfolioOverview();
    renderDecisionAudit(payload);
  } catch (error) {
    setPanelState(
      els.decisionAudit,
      "table-shell",
      "error",
      "Decision audit unavailable",
      error.message || "Decision analytics could not be loaded.",
    );
    throw error;
  }
}

function renderPolicyAnalytics(payload) {
  els.policyNote.textContent = payload.note || "";
  renderPortfolioOverview();

  if (!payload.scored_application_count) {
    setPanelState(
      els.policyAnalytics,
      "policy-grid",
      "empty",
      "Score applications to compare policies",
      "The Policy Lab needs scored applications before it can compare strategies.",
    );
    setPanelState(
      els.policySegments,
      "table-shell",
      "empty",
      "No segment policy analytics loaded",
      "Policy segment rows appear after applications are scored.",
    );
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
    setPanelState(
      els.decisionAudit,
      "table-shell",
      "empty",
      "No analyst decisions recorded",
      "Save an MFI decision to populate the audit table.",
    );
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

async function refreshStaffUsers() {
  const rows = await apiFetch("/admin/users");
  renderSimpleTable(els.staffUsers, rows, [
    ["email", "Email"],
    ["role", "Role", formatPolicyName],
    ["organization_id", "Organization"],
    ["created_at", "Created"],
  ]);
}

function syncOrganizationSelect(select, organizations) {
  if (!select) return;
  const previousValue = select.value;
  select.innerHTML = organizations
    .map(
      (organization) =>
        `<option value="${escapeHtml(organization.id)}">${escapeHtml(organization.name)}</option>`,
    )
    .join("");
  if (organizations.some((organization) => organization.id === previousValue)) {
    select.value = previousValue;
  }
}

async function refreshOrganizations() {
  const organizations = await apiFetch("/organizations");
  state.organizations = organizations;
  syncOrganizationSelect(els.applicationOrganization, organizations);
  syncOrganizationSelect(els.staffOrganization, organizations);
  renderSimpleTable(els.organizationDirectory, organizations, [
    ["name", "Organization"],
    ["id", "ID"],
    ["region", "Region"],
  ]);
  return organizations;
}

async function createOrganization(event) {
  event.preventDefault();
  const form = els.organizationForm;
  const created = await apiFetch("/admin/organizations", {
    method: "POST",
    body: JSON.stringify({
      id: form.elements.id.value.trim(),
      name: form.elements.name.value.trim(),
      region: form.elements.region.value.trim(),
    }),
  });
  form.reset();
  form.elements.region.value = "Pavlodar region, Kazakhstan";
  await Promise.all([refreshOrganizations(), refreshAudit()]);
  els.staffOrganization.value = created.id;
  showMessage(`Created ${created.name}`, "ok");
}

async function createStaffUser(event) {
  event.preventDefault();
  const form = els.staffForm;
  const created = await apiFetch("/admin/users", {
    method: "POST",
    body: JSON.stringify({
      email: form.elements.email.value.trim(),
      password: form.elements.password.value,
      role: "mfi_analyst",
      organization_id: form.elements.organization_id.value,
    }),
  });
  form.reset();
  showMessage(`Created ${created.email}`, "ok");
  await Promise.all([refreshStaffUsers(), refreshAudit()]);
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
    setPanelState(
      container,
      "table-shell",
      "empty",
      "No records loaded",
      "There is nothing to show for this view yet.",
    );
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
  window.addEventListener("hashchange", applyRoute);
  els.checkApiButton.addEventListener("click", () => {
    checkApiAndOrganizations().catch((error) => showMessage(error.message, "error"));
  });
  els.apiBase.addEventListener("change", () => {
    checkApiAndOrganizations().catch((error) => showMessage(error.message, "error"));
  });
  els.roleTabs.forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
  els.authForm.addEventListener("submit", (event) => {
    event.preventDefault();
    authenticate("login")
      .then((auth) => loadRoleWorkspace(auth.role))
      .catch((error) => showMessage(error.message, "error"));
  });
  els.registerButton.addEventListener("click", () => {
    authenticate("register")
      .then((auth) => loadRoleWorkspace(auth.role))
      .catch((error) => showMessage(error.message, "error"));
  });
  els.logoutButton.addEventListener("click", () => logoutSession());
  els.resetDemoData.addEventListener("click", () => {
    resetStaticDemoData().catch((error) => showMessage(error.message, "error"));
  });
  els.demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
      enterDemoWorkspace(button.dataset.demo, button.dataset.role)
        .catch((error) => showMessage(error.message, "error"));
    });
  });
  els.fillDemoApplication.addEventListener("click", () => {
    fillApplicationForm(demoApplication);
    els.borrowerConsent.checked = true;
  });
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
  els.exportApplications.addEventListener("click", () => {
    exportApplicationsCsv().catch((error) => showMessage(error.message, "error"));
  });
  els.scoreSelectedApplication.addEventListener("click", () => {
    scoreSelectedApplication().catch((error) => showMessage(error.message, "error"));
  });
  els.loadReviewPacket.addEventListener("click", () => {
    loadReviewPacket().catch((error) => showMessage(error.message, "error"));
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
  els.refreshUsers.addEventListener("click", () => {
    refreshStaffUsers().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshOrganizations.addEventListener("click", () => {
    refreshOrganizations().catch((error) => showMessage(error.message, "error"));
  });
  els.organizationForm.addEventListener("submit", (event) => {
    createOrganization(event).catch((error) => showMessage(error.message, "error"));
  });
  els.staffForm.addEventListener("submit", (event) => {
    createStaffUser(event).catch((error) => showMessage(error.message, "error"));
  });
  els.clearApplications.addEventListener("click", () => {
    clearApplications().catch((error) => showMessage(error.message, "error"));
  });
}

function restoreState() {
  applyRoute();
  fillApplicationForm(demoApplication);
  const lastApplicationId = localStorage.getItem("microscore.lastApplicationId");
  if (lastApplicationId) els.borrowerApplicationId.value = lastApplicationId;
}

wireEvents();
restoreState();
checkApiAndOrganizations().catch((error) => showMessage(error.message, "error"));
