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
const portfolioDashboard = window.MicroScorePortfolioDashboard || {};

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
  sessionExpiresAt: localStorage.getItem("microscore.sessionExpiresAt") || "",
  sessionTtlSeconds: Number(localStorage.getItem("microscore.sessionTtlSeconds") || 0),
  demoMode: forceStaticDemo || hostedStaticPage || localStorage.getItem("microscore.demoMode") === "static",
  selectedApplicationId: "",
  selectedReviewPacket: null,
  borrowerApplications: [],
  applications: [],
  policyAnalytics: null,
  decisionAnalytics: null,
  portfolioSimulation: null,
  simulationHistory: [],
  organizations: [],
  activeModel: null,
  applicationValidationErrors: [],
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
  mfaCode: document.querySelector("#mfaCode"),
  demoModePill: document.querySelector("#demoModePill"),
  resetDemoData: document.querySelector("#resetDemoData"),
  sessionRole: document.querySelector("#sessionRole"),
  logoutButton: document.querySelector("#logoutButton"),
  messageArea: document.querySelector("#messageArea"),
  demoButtons: document.querySelectorAll("[data-demo]"),
  applicationForm: document.querySelector("#applicationForm"),
  applicationValidationSummary: document.querySelector("#applicationValidationSummary"),
  fillDemoApplication: document.querySelector("#fillDemoApplication"),
  borrowerConsent: document.querySelector("#borrowerConsent"),
  refreshBorrowerApplication: document.querySelector("#refreshBorrowerApplication"),
  borrowerApplicationHistory: document.querySelector("#borrowerApplicationHistory"),
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
  simulationForm: document.querySelector("#simulationForm"),
  runSimulation: document.querySelector("#runSimulation"),
  simulationResults: document.querySelector("#simulationResults"),
  simulationHistory: document.querySelector("#simulationHistory"),
  refreshSimulationHistory: document.querySelector("#refreshSimulationHistory"),
  refreshAudit: document.querySelector("#refreshAudit"),
  auditTrail: document.querySelector("#auditTrail"),
  identityReadiness: document.querySelector("#identityReadiness"),
  securityReadiness: document.querySelector("#securityReadiness"),
  staffForm: document.querySelector("#staffForm"),
  staffInviteForm: document.querySelector("#staffInviteForm"),
  mfaReadiness: document.querySelector("#mfaReadiness"),
  staffUsers: document.querySelector("#staffUsers"),
  staffSessions: document.querySelector("#staffSessions"),
  staffInviteDeliveryReadiness: document.querySelector("#staffInviteDeliveryReadiness"),
  staffInviteHealth: document.querySelector("#staffInviteHealth"),
  staffInvites: document.querySelector("#staffInvites"),
  refreshUsers: document.querySelector("#refreshUsers"),
  refreshStaffSessions: document.querySelector("#refreshStaffSessions"),
  refreshStaffInvites: document.querySelector("#refreshStaffInvites"),
  applicationOrganization: document.querySelector("#applicationOrganization"),
  staffOrganization: document.querySelector("#staffOrganization"),
  staffInviteOrganization: document.querySelector("#staffInviteOrganization"),
  organizationForm: document.querySelector("#organizationForm"),
  organizationDirectory: document.querySelector("#organizationDirectory"),
  refreshOrganizations: document.querySelector("#refreshOrganizations"),
  clearApplications: document.querySelector("#clearApplications"),
  modelStatusPill: document.querySelector("#modelStatusPill"),
  modelVersionForm: document.querySelector("#modelVersionForm"),
  modelVersionRegistry: document.querySelector("#modelVersionRegistry"),
  refreshModelVersions: document.querySelector("#refreshModelVersions"),
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
  if (state.sessionExpiresAt) {
    localStorage.setItem("microscore.sessionExpiresAt", state.sessionExpiresAt);
    localStorage.setItem("microscore.sessionTtlSeconds", String(state.sessionTtlSeconds || ""));
  } else {
    localStorage.removeItem("microscore.sessionExpiresAt");
    localStorage.removeItem("microscore.sessionTtlSeconds");
  }
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
  state.sessionExpiresAt = "";
  state.sessionTtlSeconds = 0;
  resetApplicationViews();
  resetPrivilegedViews();
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
    const expiryLabel = formatSessionExpiry(state.sessionExpiresAt);
    els.sessionRole.textContent = expiryLabel
      ? `${state.role} - ${state.email} · expires ${expiryLabel}`
      : `${state.role} - ${state.email}`;
    els.sessionRole.title = state.sessionTtlSeconds
      ? `Session TTL: ${Math.round(state.sessionTtlSeconds / 60)} minutes`
      : "";
    els.sessionRole.classList.remove("muted");
    els.workspaceRoleLabel.textContent = roleLabels[state.role] || "Personal workspace";
  } else {
    els.sessionRole.textContent = "No session";
    els.sessionRole.title = "";
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

function formatAmountUnits(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) < 0 ? "-" : "";
  return `${sign}${formatMoney(Math.abs(Number(value)))} units`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatSessionExpiry(value) {
  if (!value) return "";
  const expiresAt = new Date(value);
  if (Number.isNaN(expiresAt.getTime())) return "";
  return expiresAt.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
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
  const mfaCode = els.mfaCode?.value?.trim();
  if (mfaCode) payload.mfa_code = mfaCode;
  if (mode === "register") payload.role = "borrower";

  const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
  const auth = await apiFetch(endpoint, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.token = auth.access_token;
  state.role = auth.role;
  state.email = payload.email;
  state.sessionExpiresAt = auth.session_expires_at || "";
  state.sessionTtlSeconds = Number(auth.session_ttl_seconds || 0);
  saveSession();
  navigateToRole(auth.role);
  showMessage(`Signed in as ${auth.role}`, "ok");
  return auth;
}

function fillDemoCredentials(email) {
  els.email.value = email;
  els.password.value = "password123";
  if (els.mfaCode) {
    els.mfaCode.value = ["admin@test.com", "analyst@test.com"].includes(email)
      ? "246810"
      : "";
  }
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
  if (role === "borrower") {
    await refreshBorrowerApplications();
  } else if (role === "mfi_analyst") {
    await Promise.all([
      refreshApplications(),
      refreshModelStatus(),
      refreshSimulationHistory(),
    ]);
  } else if (role === "admin") {
    await Promise.all([
      refreshAudit(),
      refreshSecurityReadiness(),
      refreshStaffUsers(),
      refreshStaffSessions(),
      refreshStaffInvites(),
      refreshOrganizations(),
      refreshModelVersions(),
      refreshModelStatus(),
      refreshSimulationHistory(),
    ]);
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

function intakeFormFieldName(path) {
  if (path === "consent_version") return "borrower_consent";
  if (path.startsWith("behavioral_signals.")) return path.split(".").pop();
  return path;
}

function renderApplicationValidation(errors = state.applicationValidationErrors) {
  state.applicationValidationErrors = errors;
  const form = els.applicationForm;
  form.querySelectorAll(".field-error").forEach((node) => node.remove());
  form.querySelectorAll(".field-invalid").forEach((node) => node.classList.remove("field-invalid"));
  Array.from(form.elements).forEach((control) => control.removeAttribute?.("aria-invalid"));

  if (!errors.length) {
    els.applicationValidationSummary.hidden = true;
    els.applicationValidationSummary.replaceChildren();
    return;
  }

  const heading = document.createElement("strong");
  heading.textContent = "Check the application before submitting";
  const list = document.createElement("ul");
  errors.forEach((error) => {
    const item = document.createElement("li");
    item.textContent = error.message;
    list.appendChild(item);

    const fieldName = intakeFormFieldName(error.field);
    const control = form.elements[fieldName];
    const label = control?.closest("label");
    if (!control || !label || label.querySelector(`[data-validation-for="${fieldName}"]`)) return;
    control.setAttribute("aria-invalid", "true");
    label.classList.add("field-invalid");
    const fieldError = document.createElement("span");
    fieldError.className = "field-error";
    fieldError.dataset.validationFor = fieldName;
    fieldError.textContent = error.message;
    label.appendChild(fieldError);
  });
  els.applicationValidationSummary.replaceChildren(heading, list);
  els.applicationValidationSummary.hidden = false;
}

function validateApplicationPayload(payload) {
  const intake = window.MicroScoreApplicationIntake;
  if (!intake) throw new Error("Application intake validation is unavailable");
  const result = intake.validateApplicationIntake(payload);
  renderApplicationValidation(result.errors);
  return result;
}

function clearApplicationFieldValidation(fieldName) {
  const remaining = state.applicationValidationErrors.filter(
    (error) => intakeFormFieldName(error.field) !== fieldName,
  );
  renderApplicationValidation(remaining);
}

function rememberApplication(id) {
  localStorage.setItem("microscore.lastApplicationId", id);
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

function reviewActionPlan(packet) {
  const riskDetail = window.MicroScoreRiskDetail;
  if (riskDetail?.buildReviewActionPlan) return riskDetail.buildReviewActionPlan(packet);
  const lifecycle = packet?.lifecycle || {};
  const allowedDecisions = Array.isArray(lifecycle.allowed_decisions)
    ? [...lifecycle.allowed_decisions]
    : [];
  return {
    stage: lifecycle.terminal ? "terminal_locked" : packet?.model_summary ? "review_ready" : "score_first",
    title: lifecycle.terminal ? "Terminal locked" : packet?.model_summary ? "Ready for decision" : "Score first",
    body: lifecycle.status_note || "",
    primary_label: lifecycle.terminal ? "Locked" : lifecycle.scoring_action === "rescore" ? "Rescore" : "Score",
    steps: [],
    blockers: [],
    blocker_count: 0,
    terminal: Boolean(lifecycle.terminal),
    scoring_action: lifecycle.scoring_action || null,
    score_enabled: Boolean(lifecycle.scoring_action) && !lifecycle.terminal,
    score_label: lifecycle.scoring_action === "rescore" ? "Rescore" : lifecycle.scoring_action === "score" ? "Score" : "Locked",
    decision_enabled: allowedDecisions.length > 0 && Boolean(packet?.model_summary) && !lifecycle.terminal,
    allowed_decisions: allowedDecisions,
    allowed_decision_labels: allowedDecisions,
    decision_count: Array.isArray(packet?.decision_history) ? packet.decision_history.length : 0,
  };
}

function resetApplicationViews() {
  localStorage.removeItem("microscore.lastApplicationId");
  state.selectedApplicationId = "";
  state.selectedReviewPacket = null;
  state.borrowerApplications = [];
  state.applications = [];
  state.policyAnalytics = null;
  state.decisionAnalytics = null;
  state.portfolioSimulation = null;
  state.simulationHistory = [];

  els.borrowerConsent.checked = false;
  renderApplicationValidation([]);
  els.borrowerApplicationHistory.className = "borrower-history empty";
  els.borrowerApplicationHistory.innerHTML = `
    <strong>No applications yet</strong>
    <span>Submit a consented application to see borrower-safe status updates here.</span>
  `;
  setPanelState(
    els.borrowerApplicationCard,
    "result-block borrower-application-card",
    "empty",
    "No application selected",
    "Submit or load an application to view its status timeline.",
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
  syncLifecycleControls(null);

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
  setPanelState(
    els.simulationResults,
    "simulation-results",
    "empty",
    "No Monte Carlo run yet",
    "Run the simulation after scored applications are loaded.",
  );
  els.simulationHistory.className = "simulation-history empty";
  els.simulationHistory.textContent = "No saved simulation runs.";
}

function resetPrivilegedViews() {
  for (const [container, label] of [
    [els.auditTrail, "No audit events loaded."],
    [els.securityReadiness, "Security readiness not loaded."],
    [els.staffUsers, "No staff users loaded."],
    [els.staffSessions, "No staff sessions loaded."],
    [els.staffInvites, "No staff invites loaded."],
    [els.organizationDirectory, "No organizations loaded."],
    [els.modelVersionRegistry, "No model versions loaded."],
  ]) {
    container.className = "table-shell empty";
    container.textContent = label;
  }
  els.identityReadiness.className = "identity-readiness empty";
  els.identityReadiness.textContent = "Identity readiness evidence not loaded.";
  els.mfaReadiness.className = "metric-grid mfa-readiness empty";
  els.mfaReadiness.textContent = "MFA readiness not loaded.";
  els.staffInviteHealth.className = "metric-grid invite-health empty";
  els.staffInviteHealth.textContent = "Invite health not loaded.";
  els.staffInviteDeliveryReadiness.className = "metric-grid invite-delivery-readiness empty";
  els.staffInviteDeliveryReadiness.textContent = "Invite delivery readiness not loaded.";
  els.modelStatusPill.className = "pill muted";
  els.modelStatusPill.textContent = "Model status unavailable";
}

function formatDisplayDate(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function borrowerStatusMeta(application = {}) {
  const status = application.status || "submitted";
  const defaults = {
    submitted: {
      label: "Submitted",
      eyebrow: "Application received",
      title: "Your application is in the MFI queue",
      body: "The MFI has the application and can prepare it for review.",
      next: "Wait for the MFI to complete the first review step.",
    },
    scored: {
      label: "Review pending",
      eyebrow: "Assessment complete",
      title: "Your application is waiting for human review",
      body: "The MFI has completed its internal assessment and still needs a person to review the application.",
      next: "Check back for a recorded decision or a manual review update.",
    },
    under_review: {
      label: "In review",
      eyebrow: "Human review",
      title: "An MFI reviewer is looking at your application",
      body: "The MFI has marked the application for manual review. No final outcome has been recorded yet.",
      next: "Watch this page for a final update from the MFI.",
    },
    approved: {
      label: "Approved",
      eyebrow: "Final outcome",
      title: "The MFI recorded an approval",
      body: "This is the final status shown in the demo portal. Follow the MFI's normal borrower communication channel for next steps.",
      next: "No more workflow changes are shown here after a final decision.",
    },
    declined: {
      label: "Not approved",
      eyebrow: "Final outcome",
      title: "The MFI recorded a decline decision",
      body: "This is the final status shown in the demo portal. The portal does not expose internal analyst notes, scores, or policy details.",
      next: "No more workflow changes are shown here after a final decision.",
    },
  };
  return defaults[status] || {
    label: formatPolicyName(status),
    eyebrow: "Application status",
    title: "Application status updated",
    body: application.status_message || "The MFI workflow status changed.",
    next: "Refresh this page for the latest borrower-safe status.",
  };
}

function renderApplication(application) {
  if (state.role === "borrower") return renderBorrowerApplication(application);

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
    ${renderLifecycleProgress(application)}
    ${decision}
    ${score ? renderScore(score) : ""}
    ${timeline}
  `;
}

function renderBorrowerApplication(application) {
  const meta = borrowerStatusMeta(application);
  const terminalClass = application.terminal ? " terminal" : "";
  const purpose = application.purpose
    ? escapeHtml(application.purpose)
    : "No purpose provided";
  const district = application.district || application.settlement_type
    ? `${application.district || "District not set"}${application.settlement_type ? ` / ${formatPolicyName(application.settlement_type)}` : ""}`
    : "Location not provided";
  return `
    <article class="borrower-portal-card borrower-status-${escapeHtml(application.status || "submitted")}${terminalClass}">
      <section class="borrower-status-banner">
        <div>
          <span>${escapeHtml(meta.eyebrow)}</span>
          <strong>${escapeHtml(meta.title)}</strong>
          <p>${escapeHtml(application.status_message || meta.body)}</p>
        </div>
        <em class="pill status-${escapeHtml(application.status || "submitted")}">${escapeHtml(meta.label)}</em>
      </section>
      <div class="borrower-summary-grid">
        <div><span>Requested amount</span><strong>${formatMoney(application.requested_amount)}</strong></div>
        <div><span>Submitted</span><strong>${escapeHtml(formatDisplayDate(application.created_at))}</strong></div>
        <div><span>MFI organization</span><strong>${escapeHtml(application.organization_id || "assigned")}</strong></div>
        <div><span>Application ID</span><strong>${escapeHtml(application.id)}</strong></div>
      </div>
      ${renderLifecycleProgress(application)}
      <section class="borrower-next-step">
        <div>
          <span>What this means</span>
          <p>${escapeHtml(meta.body)}</p>
        </div>
        <div>
          <span>Next update</span>
          <p>${escapeHtml(meta.next)}</p>
        </div>
      </section>
      <section class="borrower-application-facts">
        <h4>Application details</h4>
        <dl>
          <div><dt>Purpose</dt><dd>${purpose}</dd></div>
          <div><dt>Location</dt><dd>${escapeHtml(district)}</dd></div>
          <div><dt>Status updated</dt><dd>${escapeHtml(formatDisplayDate(application.scored_at || application.created_at))}</dd></div>
        </dl>
      </section>
      ${renderBorrowerTimeline(application.timeline_events)}
      <aside class="borrower-privacy-note">
        This borrower portal shows application status only. It does not show internal scores, analyst notes, policy names, raw behavioral signals, staff identity, or review-plan details.
      </aside>
    </article>
  `;
}

function renderLifecycleProgress(application) {
  const statuses = ["submitted", "scored", "under_review", "decision"];
  const currentIndex = application.status === "approved" || application.status === "declined"
    ? 3
    : Math.max(0, statuses.indexOf(application.status));
  const finalLabel = application.status === "approved"
    ? "Approved"
    : application.status === "declined"
      ? "Declined"
      : "Decision";
  const labels = ["Submitted", "Scored", "Human review", finalLabel];
  const steps = labels.map((label, index) => {
    const stateClass = index < currentIndex ? "complete" : index === currentIndex ? "active" : "pending";
    const current = stateClass === "active" ? ' aria-current="step"' : "";
    return `<li class="${stateClass}"${current}><span>${index + 1}</span><strong>${escapeHtml(label)}</strong></li>`;
  }).join("");
  const message = application.status_message
    ? `<p class="lifecycle-message">${escapeHtml(application.status_message)}</p>`
    : "";
  return `<div class="lifecycle-progress"><ol>${steps}</ol>${message}</div>`;
}

function renderBorrowerTimeline(events) {
  const safeEvents = Array.isArray(events) ? events : [];
  if (!safeEvents.length) {
    return `
      <div class="timeline-block borrower-timeline">
        <h4>Status timeline</h4>
        <p class="tiny-text">Timeline updates will appear after the MFI workflow records a borrower-safe event.</p>
      </div>
    `;
  }

  const rows = safeEvents
    .map((event) => {
      const status = event.details?.status ? formatPolicyName(event.details.status) : "";
      return `
        <li>
          <div>
            <strong>${escapeHtml(event.title || formatPolicyName(event.action))}</strong>
            <span>${status ? `Status: ${escapeHtml(status)}` : "Borrower-safe update"}</span>
          </div>
          <em>${escapeHtml(formatDisplayDate(event.created_at))}</em>
        </li>
      `;
    })
    .join("");
  return `
    <div class="timeline-block borrower-timeline">
      <h4>Status timeline</h4>
      <ol>${rows}</ol>
    </div>
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
            <span>${escapeHtml(event.actor_email || (state.role === "borrower" ? "MFI workflow" : "system"))}</span>
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
  const payload = applicationPayload();
  const validation = validateApplicationPayload(payload);
  if (!validation.valid) {
    showMessage("Check the highlighted application fields", "error");
    els.applicationValidationSummary.focus();
    return;
  }
  const application = await apiFetch("/applications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  renderApplicationValidation([]);
  rememberApplication(application.id);
  await refreshBorrowerApplications(application.id);
  showMessage("Application submitted", "ok");
}

async function openBorrowerApplication(id) {
  state.selectedApplicationId = id;
  renderBorrowerApplicationHistory(state.borrowerApplications);
  setPanelState(
    els.borrowerApplicationCard,
    "result-block borrower-application-card",
    "loading",
    "Opening application status",
    "Loading the borrower-safe status timeline.",
  );
  try {
    const cached = state.borrowerApplications.find((application) => application.id === id);
    const application = cached || await apiFetch(`/applications/${encodeURIComponent(id)}`);
    const applicationWithTimeline = await attachApplicationTimeline(application);
    els.borrowerApplicationCard.className = "result-block borrower-application-card";
    els.borrowerApplicationCard.innerHTML = renderApplication(applicationWithTimeline);
    rememberApplication(id);
    return applicationWithTimeline;
  } catch (error) {
    setPanelState(
      els.borrowerApplicationCard,
      "result-block borrower-application-card",
      "error",
      "Application status unavailable",
      error.message || "The borrower-safe status view could not be loaded.",
    );
    throw error;
  }
}

async function refreshBorrowerApplications(preferredId = "") {
  setPanelState(
    els.borrowerApplicationHistory,
    "borrower-history",
    "loading",
    "Loading application history",
    "Fetching your borrower-safe status list.",
  );
  try {
    const applications = await apiFetch("/applications");
    state.borrowerApplications = applications;
    renderBorrowerApplicationHistory(applications);
    if (!applications.length) {
      state.selectedApplicationId = "";
      setPanelState(
        els.borrowerApplicationCard,
        "result-block borrower-application-card",
        "empty",
        "No application selected",
        "Submit an application to start its lifecycle.",
      );
      return applications;
    }
    const rememberedId = preferredId || localStorage.getItem("microscore.lastApplicationId") || "";
    const selectedId = applications.some((application) => application.id === rememberedId)
      ? rememberedId
      : applications[0].id;
    await openBorrowerApplication(selectedId);
    return applications;
  } catch (error) {
    state.borrowerApplications = [];
    state.selectedApplicationId = "";
    setPanelState(
      els.borrowerApplicationHistory,
      "borrower-history",
      "error",
      "Application history unavailable",
      error.message || "Your borrower-safe application history could not be loaded.",
    );
    setPanelState(
      els.borrowerApplicationCard,
      "result-block borrower-application-card",
      "error",
      "Status unavailable",
      "Refresh the history after the connection is restored.",
    );
    throw error;
  }
}

function renderBorrowerApplicationHistory(applications) {
  if (!applications.length) {
    els.borrowerApplicationHistory.className = "borrower-history empty";
    els.borrowerApplicationHistory.innerHTML = `
      <strong>No applications yet</strong>
      <span>Submit a consented application to see borrower-safe status updates here.</span>
    `;
    return;
  }
  els.borrowerApplicationHistory.className = "borrower-history";
  els.borrowerApplicationHistory.innerHTML = applications.map((application) => {
    const selected = application.id === state.selectedApplicationId;
    const meta = borrowerStatusMeta(application);
    const purpose = application.purpose || application.district || "Application";
    return `
      <button class="borrower-history-row ${selected ? "selected" : ""} ${application.terminal ? "terminal" : ""}" type="button" aria-pressed="${selected}" ${selected ? 'aria-current="true"' : ""} data-borrower-application-id="${escapeHtml(application.id)}">
        <span class="borrower-history-main">
          <strong>${formatAmountUnits(application.requested_amount)}</strong>
          <em>${escapeHtml(purpose)}</em>
        </span>
        <span class="pill status-${escapeHtml(application.status)}">${escapeHtml(meta.label)}</span>
        <span class="borrower-history-meta">
          <em>${escapeHtml(formatDisplayDate(application.created_at))}</em>
          <em>${escapeHtml(application.organization_id || "assigned MFI")}</em>
        </span>
      </button>
    `;
  }).join("");
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

function selectApplication(applicationId, options = {}) {
  const { loadDetail = true } = options;
  state.selectedApplicationId = applicationId;
  const application = state.applications.find((item) => item.id === applicationId);
  const packet = state.selectedReviewPacket?.application_id === applicationId
    ? state.selectedReviewPacket
    : null;
  if (!packet) state.selectedReviewPacket = null;
  syncLifecycleControls(application, packet);
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
  if (application && loadDetail) {
    loadReviewPacket(application.id).catch((error) =>
      showMessage(error.message, "error"),
    );
  }
}

function syncLifecycleControls(application, packet = null) {
  const actionPlan = packet ? reviewActionPlan(packet) : null;
  const terminal = actionPlan ? actionPlan.terminal : ["approved", "declined"].includes(application?.status);
  const hasScore = actionPlan ? Boolean(packet?.model_summary) : Boolean(application?.score_result);
  const allowedDecisions = actionPlan?.allowed_decisions || (
    application?.status === "scored"
      ? ["review", "approve", "decline"]
      : application?.status === "under_review"
        ? ["approve", "decline"]
        : []
  );
  const scoreEnabled = actionPlan
    ? actionPlan.score_enabled
    : Boolean(application) && !terminal;

  els.scoreSelectedApplication.disabled = !scoreEnabled;
  els.scoreSelectedApplication.textContent = actionPlan?.score_label || (terminal ? "Finalized" : hasScore ? "Rescore" : "Score");
  const decisionSelect = els.decisionForm.elements.decision;
  Array.from(decisionSelect.options).forEach((option) => {
    option.disabled = !allowedDecisions.includes(option.value);
  });
  if (allowedDecisions.length && !allowedDecisions.includes(decisionSelect.value)) {
    decisionSelect.value = allowedDecisions[0];
  }
  const decisionDisabled = actionPlan
    ? !actionPlan.decision_enabled
    : !application || !hasScore || terminal;
  Array.from(els.decisionForm.elements).forEach((field) => {
    field.disabled = decisionDisabled;
  });
  const submitButton = els.decisionForm.querySelector("button[type='submit']");
  if (submitButton) {
    submitButton.textContent = terminal ? "Locked" : decisionDisabled ? "Open review packet" : "Save decision";
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

  const dashboard = portfolioDashboard.summarizePortfolioDashboard
    ? portfolioDashboard.summarizePortfolioDashboard(state.applications)
    : summarizePortfolioDashboardFallback(state.applications);
  const districtRows = renderDistrictRiskRows(dashboard.districtRows);
  const settlementRows = renderSettlementTypeRows(dashboard.settlementRows);
  const policySnapshot = renderPortfolioPolicySnapshot(state.policyAnalytics);
  const decisionSnapshot = renderPortfolioDecisionSnapshot(state.decisionAnalytics);
  const topDistrict = dashboard.topDistrict
    ? `${dashboard.topDistrict.key} (${formatPercent(dashboard.topDistrict.share)})`
    : "-";

  els.portfolioOverview.className = "portfolio-overview";
  els.portfolioOverview.innerHTML = `
    <div class="portfolio-metrics">
      <div class="metric"><span>Applications</span><strong>${dashboard.applicationCount}</strong></div>
      <div class="metric"><span>Scored</span><strong>${dashboard.scoredCount}</strong></div>
      <div class="metric"><span>Avg risk</span><strong>${formatPercent(dashboard.avgRisk)}</strong></div>
      <div class="metric"><span>High risk</span><strong class="risk-high">${formatPercent(dashboard.highRiskShare)}</strong></div>
      <div class="metric"><span>Top district</span><strong>${escapeHtml(topDistrict)}</strong></div>
      <div class="metric"><span>Rural/peri share</span><strong>${formatPercent(dashboard.contextualSettlementShare)}</strong></div>
    </div>
    <div class="portfolio-grid">
      <section class="portfolio-card">
        <h4>Risk bands</h4>
        <div class="risk-band-chart">
          ${dashboard.riskBandRows.map(renderRiskBandBar).join("")}
        </div>
      </section>
      <section class="portfolio-card">
        <h4>District risk</h4>
        <div class="district-bars">${districtRows}</div>
      </section>
      <section class="portfolio-card">
        <h4>Settlement mix</h4>
        <div class="settlement-bars">${settlementRows}</div>
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
    <p class="portfolio-snapshot-note">
      Screenshot snapshot: ${dashboard.scoredCount} scored applications, top district ${escapeHtml(topDistrict)}, contextual rural/peri-urban share ${formatPercent(dashboard.contextualSettlementShare)}.
      Synthetic demo analytics only.
    </p>
  `;
}

function summarizePortfolioDashboardFallback(applications) {
  const scored = scoredApplications(applications);
  const probabilities = scored.map((application) => application.score_result.high_risk_probability);
  const highRiskShare = scored.length
    ? scored.filter((application) => application.score_result.risk_band === "high").length / scored.length
    : 0;
  const riskCounts = {
    low: 0,
    medium: 0,
    high: 0,
    ...countBy(scored, (application) => application.score_result.risk_band),
  };
  const districtRows = portfolioSegmentRowsFallback(
    scored,
    (application) => application.district || application.behavioral_signals?.pavlodar_district,
    { limit: 7 },
  );
  const allDistrictRows = portfolioSegmentRowsFallback(
    scored,
    (application) => application.district || application.behavioral_signals?.pavlodar_district,
    { sort: "count" },
  );
  const settlementRows = portfolioSegmentRowsFallback(
    scored,
    (application) => application.settlement_type || application.behavioral_signals?.settlement_type,
    { order: ["urban", "industrial_city", "peri_urban", "rural", "unknown"] },
  );
  const contextualCount = settlementRows
    .filter((row) => ["rural", "peri_urban"].includes(row.key))
    .reduce((total, row) => total + row.count, 0);

  return {
    applicationCount: applications.length,
    scoredCount: scored.length,
    avgRisk: average(probabilities),
    highRiskShare,
    contextualSettlementShare: scored.length ? contextualCount / scored.length : 0,
    topDistrict: allDistrictRows[0] || null,
    riskBandRows: ["low", "medium", "high"].map((band) => ({
      key: band,
      count: riskCounts[band],
      share: scored.length ? riskCounts[band] / scored.length : 0,
    })),
    districtRows,
    settlementRows,
  };
}

function portfolioSegmentRowsFallback(scored, getKey, options = {}) {
  if (!scored.length) return [];
  const groups = {};
  scored.forEach((application) => {
    const key = getKey(application) || "unknown";
    groups[key] = groups[key] || [];
    groups[key].push(application.score_result.high_risk_probability);
  });
  const rows = Object.entries(groups).map(([key, values]) => ({
    key,
    count: values.length,
    share: values.length / scored.length,
    avgRisk: average(values),
  }));
  if (options.order) {
    const orderMap = new Map(options.order.map((item, index) => [item, index]));
    rows.sort((left, right) => (
      (orderMap.get(left.key) ?? options.order.length) - (orderMap.get(right.key) ?? options.order.length)
      || right.count - left.count
    ));
  } else if (options.sort === "count") {
    rows.sort((left, right) => right.count - left.count || right.avgRisk - left.avgRisk);
  } else {
    rows.sort((left, right) => right.avgRisk - left.avgRisk || right.count - left.count);
  }
  return typeof options.limit === "number" ? rows.slice(0, options.limit) : rows;
}

function renderRiskBandBar(row) {
  const label = row.key;
  const count = row.count || 0;
  const rate = row.share || 0;
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

function renderDistrictRiskRows(rows) {
  if (!rows.length) return "<p class=\"empty tiny-text\">No scored applications yet.</p>";

  return rows
    .map(
      (row) => `
        <div class="district-risk-row">
          <div>
            <strong>${escapeHtml(row.key)}</strong>
            <span>${row.count} applications · ${formatPercent(row.share)} of scored</span>
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

function renderSettlementTypeRows(rows) {
  if (!rows.length) return "<p class=\"empty tiny-text\">No scored applications yet.</p>";

  return rows
    .map(
      (row) => `
        <div class="settlement-risk-row">
          <div>
            <strong>${escapeHtml(formatPolicyName(row.key))}</strong>
            <span>${row.count} applications · avg risk ${formatPercent(row.avgRisk)}</span>
          </div>
          <div class="portfolio-bar">
            <span class="settlement-fill-${escapeHtml(row.key)}" style="width: ${clampPercent(row.share)}%"></span>
          </div>
          <em>${formatPercent(row.share)}</em>
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
      selectApplication(scored.id, { loadDetail: false });
      await loadReviewPacket(scored.id);
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
  const selected = state.applications.find((item) => item.id === state.selectedApplicationId);
  syncLifecycleControls(selected, state.selectedReviewPacket);
}

async function loadReviewPacket(applicationId = state.selectedApplicationId) {
  if (!applicationId) {
    showMessage("Select an application first", "error");
    return;
  }

  return await withButtonBusy(els.loadReviewPacket, "Opening...", async () => {
    setPanelState(
      els.reviewPacket,
      "result-block",
      "loading",
      "Opening review packet",
      "Collecting governance flags, factors, and timeline events.",
    );
    try {
      const packet = await apiFetch(
        `/mfi/applications/${encodeURIComponent(applicationId)}/review-packet`,
      );
      if (state.selectedApplicationId !== applicationId) return packet;
      state.selectedReviewPacket = packet;
      const application = state.applications.find((item) => item.id === applicationId);
      syncLifecycleControls(application, packet);
      els.reviewPacket.className = "result-block";
      els.reviewPacket.innerHTML = renderReviewPacket(packet);
      return packet;
    } catch (error) {
      if (state.selectedApplicationId !== applicationId) return null;
      state.selectedReviewPacket = null;
      const application = state.applications.find((item) => item.id === applicationId);
      syncLifecycleControls(application);
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
  const affordability = packet.affordability || {};
  const lifecycle = packet.lifecycle || {};
  const detailSummary = window.MicroScoreRiskDetail?.summarizeReviewPacket(packet) || {
    readiness_label: "Review detail",
    required_checks: 0,
    completed_checks: 0,
    decision_count: (packet.decision_history || []).length,
  };
  const actionPlan = detailSummary.action_plan || reviewActionPlan(packet);
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
  const allowedActions = (lifecycle.allowed_decisions || []).length
    ? lifecycle.allowed_decisions.map((action) => `<span>${escapeHtml(formatPolicyName(action))}</span>`).join("")
    : "<span>No decision mutations allowed</span>";
  const decisionHistory = (packet.decision_history || []).length
    ? `<ol class="decision-history">${packet.decision_history.map((row) => `
        <li class="decision-${escapeHtml(row.decision)}">
          <div><strong>${escapeHtml(formatPolicyName(row.decision))}</strong><span>${escapeHtml(row.actor_email)}</span></div>
          <em>${escapeHtml(row.created_at)}</em>
          <p>${escapeHtml(row.note || "No note recorded.")}</p>
        </li>
      `).join("")}</ol>`
    : "<p class=\"tiny-text\">No analyst decisions recorded.</p>";

  return `
    <div class="review-packet">
      <div class="packet-heading">
        <div>
          <span>Review packet</span>
          <strong>${escapeHtml(packet.application_id)}</strong>
        </div>
        <em>${escapeHtml(packet.generated_at)}</em>
      </div>
      <div class="risk-readiness ${lifecycle.terminal ? "terminal" : "open"}">
        <div><span>Review readiness</span><strong>${escapeHtml(detailSummary.readiness_label)}</strong></div>
        <div><span>Required / complete</span><strong>${detailSummary.required_checks} / ${detailSummary.completed_checks}</strong></div>
        <div><span>Decision history</span><strong>${detailSummary.decision_count}</strong></div>
      </div>
      ${renderReviewActionPlan(actionPlan)}
      <div class="metric-grid">
        <div class="metric"><span>Risk</span><strong class="${model ? `risk-${escapeHtml(model.risk_band)}` : ""}">${model ? escapeHtml(model.risk_band) : "not scored"}</strong></div>
        <div class="metric"><span>Probability</span><strong>${model ? formatPercent(model.high_risk_probability) : "-"}</strong></div>
        <div class="metric"><span>Proxy delta</span><strong>${model ? formatPercent(model.proxy_sensitivity_delta) : "-"}</strong></div>
        <div class="metric"><span>Decision</span><strong>${decision ? escapeHtml(formatPolicyName(decision.decision)) : "not recorded"}</strong></div>
      </div>
      ${modelUseNotice}
      <section class="lifecycle-actions">
        <div><span>Lifecycle</span><strong>${escapeHtml(formatPolicyName(lifecycle.status || packet.application.status))}</strong></div>
        <div><span>Scoring</span><strong>${escapeHtml(formatPolicyName(lifecycle.scoring_action || "locked"))}</strong></div>
        <div class="packet-flags">${allowedActions}</div>
        <p>${escapeHtml(lifecycle.status_note || "")}</p>
      </section>
      <div class="packet-flags">${flags || "<span>No governance flags</span>"}</div>
      <section class="affordability-panel">
        <div class="section-heading"><span>Affordability snapshot</span><em>${formatPercent(affordability.completeness)}</em></div>
        <div class="metric-grid">
          <div class="metric"><span>Annual income</span><strong>${formatAmountUnits(affordability.annual_income)}</strong></div>
          <div class="metric"><span>Outstanding debt</span><strong>${formatAmountUnits(affordability.total_outstanding_debt)}</strong></div>
          <div class="metric"><span>Debt / income</span><strong>${formatPercent(affordability.debt_to_income_ratio)}</strong></div>
          <div class="metric"><span>Request / income</span><strong>${formatPercent(affordability.requested_amount_to_income_ratio)}</strong></div>
        </div>
        <p>${escapeHtml(affordability.note || "")}</p>
      </section>
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
      <section class="decision-history-panel"><h4>Decision history</h4>${decisionHistory}</section>
      ${timeline}
      <p class="packet-note">${escapeHtml(packet.audit_note)}</p>
    </div>
  `;
}

function renderReviewActionPlan(actionPlan) {
  const steps = actionPlan.steps?.length
    ? actionPlan.steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")
    : "<li>Refresh the selected review packet before changing workflow state.</li>";
  const blockers = actionPlan.blockers?.length
    ? `<ul class="action-plan-blockers">${actionPlan.blockers.map((item) => `
        <li>
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.evidence || item.code || "required")}</span>
        </li>
      `).join("")}</ul>`
    : "<p class=\"tiny-text\">No required checklist blockers.</p>";
  const allowedDecisions = actionPlan.allowed_decisions?.length
    ? actionPlan.allowed_decisions.map((decision) => `<span>${escapeHtml(formatPolicyName(decision))}</span>`).join("")
    : "<span>No decision actions allowed</span>";
  return `
    <section class="review-action-plan action-stage-${escapeHtml(actionPlan.stage)}">
      <div class="section-heading">
        <span>Action plan</span>
        <em>${escapeHtml(actionPlan.primary_label)}</em>
      </div>
      <h4>${escapeHtml(actionPlan.title)}</h4>
      <p>${escapeHtml(actionPlan.body)}</p>
      <ol class="action-plan-steps">${steps}</ol>
      <div class="action-plan-grid">
        <div>
          <strong>Checklist blockers</strong>
          ${blockers}
        </div>
        <div>
          <strong>Allowed decisions</strong>
          <div class="packet-flags">${allowedDecisions}</div>
        </div>
      </div>
    </section>
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
  const packet = state.selectedReviewPacket?.application_id === state.selectedApplicationId
    ? state.selectedReviewPacket
    : await loadReviewPacket(state.selectedApplicationId);
  const actionPlan = packet ? reviewActionPlan(packet) : null;
  const selectedDecision = els.decisionForm.elements.decision.value;
  if (!actionPlan?.decision_enabled) {
    showMessage(actionPlan?.terminal ? "Application is locked after a terminal decision" : "Open the review packet before saving a decision", "error");
    return;
  }
  if (!actionPlan.allowed_decisions.includes(selectedDecision)) {
    showMessage("Selected decision is not available for this lifecycle state", "error");
    return;
  }

  const updated = await apiFetch(`/mfi/applications/${encodeURIComponent(state.selectedApplicationId)}/decision`, {
    method: "POST",
    body: JSON.stringify(decisionPayload()),
  });
  state.applications = state.applications.map((item) => (item.id === updated.id ? updated : item));
  selectApplication(updated.id, { loadDetail: false });
  await refreshDecisionAnalytics();
  await loadReviewPacket(updated.id);
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

function simulationPayload() {
  const form = els.simulationForm;
  return {
    iterations: Number(form.elements.iterations.value),
    seed: Number(form.elements.seed.value),
    policy: form.elements.policy.value,
    scenarios: ["baseline", "adverse", "severe"],
    review_approval_rate: Number(form.elements.review_approval_rate.value),
    interest_margin_rate: Number(form.elements.interest_margin_rate.value),
    loss_given_default: Number(form.elements.loss_given_default.value),
    operating_cost_per_approved: Number(form.elements.operating_cost_per_approved.value),
    macro_volatility: Number(form.elements.macro_volatility.value),
    calibration_volatility: Number(form.elements.calibration_volatility.value),
  };
}

async function runPortfolioSimulation() {
  setPanelState(
    els.simulationResults,
    "simulation-results",
    "loading",
    "Running Monte Carlo simulation",
    "Applying paired macro, calibration, review, and default draws.",
  );
  try {
    const payload = await apiFetch("/mfi/simulations/portfolio", {
      method: "POST",
      body: JSON.stringify(simulationPayload()),
    });
    state.portfolioSimulation = payload;
    renderPortfolioSimulation(payload);
    await refreshSimulationHistory();
    showMessage(`Completed ${formatMoney(payload.assumptions.iterations)} Monte Carlo iterations`, "ok");
    return payload;
  } catch (error) {
    setPanelState(
      els.simulationResults,
      "simulation-results",
      "error",
      "Simulation unavailable",
      error.message || "Monte Carlo simulation could not be completed.",
    );
    throw error;
  }
}

async function refreshSimulationHistory() {
  const rows = await apiFetch("/mfi/simulations");
  state.simulationHistory = rows;
  renderSimulationHistory(rows);
  return rows;
}

function renderSimulationHistory(rows) {
  if (!rows?.length) {
    els.simulationHistory.className = "simulation-history empty";
    els.simulationHistory.textContent = "No saved simulation runs.";
    return;
  }

  els.simulationHistory.className = "simulation-history";
  els.simulationHistory.innerHTML = rows.map((row) => {
    const baseline = (row.scenario_summary || []).find((scenario) => scenario.scenario === "baseline");
    const result = baseline ? formatAmountUnits(baseline.portfolio_result_p50) : "-";
    const loss = baseline ? formatPercent(baseline.probability_of_loss) : "-";
    const fingerprint = String(row.portfolio_fingerprint || "");
    return `
      <button class="simulation-history-row" type="button" data-simulation-id="${escapeHtml(row.simulation_id)}">
        <span><strong>${escapeHtml(formatPolicyName(row.policy))}</strong><em>${escapeHtml(row.generated_at)}</em></span>
        <span><strong>${result}</strong><em>Baseline / loss ${loss}</em></span>
        <span><strong>${formatMoney(row.iterations)} draws</strong><em>${escapeHtml(fingerprint.slice(0, 12))}…</em></span>
      </button>
    `;
  }).join("");
}

async function loadStoredSimulation(simulationId) {
  const payload = await apiFetch(`/mfi/simulations/${encodeURIComponent(simulationId)}`);
  state.portfolioSimulation = payload;
  renderPortfolioSimulation(payload);
  showMessage(`Loaded saved Monte Carlo run ${simulationId}`, "ok");
  return payload;
}

function renderPortfolioSimulation(payload) {
  const models = (payload.model_versions || []).join(", ") || "not recorded";
  const scenarioCards = (payload.scenarios || []).map(renderSimulationScenario).join("");
  const warnings = (payload.warnings || []).length
    ? `<ul class="simulation-warnings">${payload.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
    : "";
  els.simulationResults.className = "simulation-results";
  els.simulationResults.innerHTML = `
    <div class="simulation-summary">
      <div><span>Policy</span><strong>${escapeHtml(formatPolicyName(payload.policy.name))}</strong></div>
      <div><span>Scored portfolio</span><strong>${escapeHtml(payload.scored_application_count)}</strong></div>
      <div><span>Iterations / seed</span><strong>${formatMoney(payload.assumptions.iterations)} / ${escapeHtml(payload.assumptions.seed)}</strong></div>
      <div><span>Score versions</span><strong>${escapeHtml(models)}</strong></div>
      <div><span>Portfolio fingerprint</span><strong title="${escapeHtml(payload.portfolio_fingerprint)}">${escapeHtml(payload.portfolio_fingerprint.slice(0, 16))}…</strong></div>
      <div><span>Saved run</span><strong>${escapeHtml(payload.simulation_id)}</strong></div>
    </div>
    ${warnings}
    <div class="simulation-scenarios">${scenarioCards}</div>
    <p class="simulation-note">
      Review approval ${formatPercent(payload.assumptions.review_approval_rate)} / margin ${formatPercent(payload.assumptions.interest_margin_rate)} / LGD ${formatPercent(payload.assumptions.loss_given_default)} / macro volatility ${Number(payload.assumptions.macro_volatility).toFixed(2)} / calibration volatility ${Number(payload.assumptions.calibration_volatility).toFixed(2)}.
    </p>
    <p class="simulation-note"><strong>Boundary:</strong> ${escapeHtml(payload.note)}</p>
  `;
}

function renderSimulationScenario(row) {
  const lossWidth = clampPercent(row.probability_of_loss);
  const approved = row.approved_count;
  const defaults = row.default_count;
  const result = row.portfolio_result;
  const diagnostics = row.diagnostics || {};
  return `
    <article class="simulation-card ${escapeHtml(row.scenario)}">
      <div class="simulation-card-heading">
        <strong>${escapeHtml(formatPolicyName(row.scenario))}</strong>
        <em>log-odds shift ${Number(row.log_odds_shift).toFixed(2)}</em>
      </div>
      <div class="simulation-card-metrics">
        <div class="simulation-metric"><span>Median result</span><strong>${formatAmountUnits(result.p50)}</strong></div>
        <div class="simulation-metric"><span>Loss probability</span><strong>${formatPercent(row.probability_of_loss)}</strong></div>
        <div class="simulation-metric"><span>Approved mean</span><strong>${Number(approved.mean).toFixed(1)}</strong></div>
        <div class="simulation-metric"><span>Defaults mean</span><strong>${Number(defaults.mean).toFixed(1)}</strong></div>
        <div class="simulation-metric"><span>Median exposure</span><strong>${formatAmountUnits(row.approved_exposure.p50)}</strong></div>
        <div class="simulation-metric"><span>Mean stressed risk</span><strong>${formatPercent(row.mean_stressed_probability)}</strong></div>
      </div>
      <div class="loss-meter" aria-label="Probability of negative portfolio result"><span style="width:${lossWidth}%"></span></div>
      <p class="simulation-range">Result P05-P95: ${formatAmountUnits(result.p05)} to ${formatAmountUnits(result.p95)}</p>
      <p class="simulation-range">Defaults P05-P95: ${Number(defaults.p05).toFixed(1)} to ${Number(defaults.p95).toFixed(1)} / approved ${Number(approved.p05).toFixed(1)} to ${Number(approved.p95).toFixed(1)}</p>
      <p class="simulation-range">Monte Carlo SE: result mean ±${formatAmountUnits(diagnostics.portfolio_result_mean_standard_error || 0)} / defaults mean ±${Number(diagnostics.default_count_mean_standard_error || 0).toFixed(3)} / loss probability ±${formatPercent(diagnostics.loss_probability_standard_error || 0)}</p>
    </article>
  `;
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

function renderSecurityReadiness(readiness) {
  if (!els.securityReadiness) return;
  const statusClass = readiness.status === "blocked"
    ? "risk-high"
    : readiness.status === "review"
      ? "risk-medium"
      : "risk-low";
  const rows = (readiness.checks || [])
    .map((check) => `
      <tr>
        <td>${escapeHtml(check.label)}</td>
        <td>${escapeHtml(formatPolicyName(check.status))}</td>
        <td>${escapeHtml(check.summary)}</td>
        <td>${escapeHtml(check.action)}</td>
      </tr>
    `)
    .join("");
  els.securityReadiness.className = "table-shell security-readiness";
  els.securityReadiness.innerHTML = `
    <div class="metric-grid">
      <div class="metric">
        <span>Pre-pilot status</span>
        <strong class="${statusClass}">${escapeHtml(formatPolicyName(readiness.status))}</strong>
      </div>
      <div class="metric">
        <span>Blockers</span>
        <strong>${Number(readiness.blockers_count || 0)}</strong>
      </div>
      <div class="metric">
        <span>Warnings</span>
        <strong>${Number(readiness.warnings_count || 0)}</strong>
      </div>
      <p class="tiny-text full-width">${escapeHtml(readiness.limitation || "Security readiness is a prototype control summary.")}</p>
    </div>
    <table>
      <thead>
        <tr>
          <th>Check</th>
          <th>Status</th>
          <th>Summary</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function severityClass(status) {
  if (["blocker", "blocked", "fail"].includes(status)) return "severity-blocker";
  if (["warning", "review", "attention"].includes(status)) return "severity-warning";
  if (["info", "prototype", "manual"].includes(status)) return "severity-info";
  return "severity-pass";
}

function severityLabel(status) {
  if (status === "pass") return "Ready";
  if (status === "blocker") return "Blocker";
  if (status === "warning") return "Warning";
  if (status === "info") return "Info";
  return formatPolicyName(status || "unknown");
}

function renderIdentityEvidenceRow(row) {
  return `
    <article class="evidence-row ${severityClass(row.severity || row.status)}">
      <div>
        <span>${escapeHtml(severityLabel(row.severity || row.status))}</span>
        <strong>${escapeHtml(row.label || formatPolicyName(row.key))}</strong>
      </div>
      <p>${escapeHtml(row.summary || "No summary provided.")}</p>
      <em>${escapeHtml(row.action || "Keep this control under review before pilot use.")}</em>
    </article>
  `;
}

function renderIdentityReadiness(payload) {
  if (!els.identityReadiness) return;
  if (!payload) {
    setPanelState(
      els.identityReadiness,
      "identity-readiness",
      "empty",
      "No identity evidence loaded",
      "Refresh the admin workspace to load the Security Evidence Room.",
    );
    return;
  }

  const statusClass = payload.status === "blocked"
    ? "risk-high"
    : payload.status === "review"
      ? "risk-medium"
      : "risk-low";
  const components = payload.components || [];
  const blockers = payload.production_blockers || [];
  const warnings = components.filter((row) => row.status === "warning");
  const controls = payload.next_required_controls || [];
  const componentByKey = new Map(components.map((row) => [row.key, row]));
  const rows = components.map(renderIdentityEvidenceRow).join("");
  const nextControls = controls.length
    ? controls
      .map((item) => `<li><strong>${escapeHtml(formatPolicyName(item.key))}:</strong> ${escapeHtml(item.action || item.summary || "Keep this control under review.")}</li>`)
      .join("")
    : "<li>Continue monitoring identity, invite delivery, sessions, tenant isolation, and storage controls.</li>";
  const provider = componentByKey.get("auth_provider") || {};
  const invite = componentByKey.get("invite_delivery") || {};
  const mfa = componentByKey.get("mfa_posture") || {};
  const sessions = componentByKey.get("session_control") || {};
  const tenant = componentByKey.get("tenant_isolation") || {};
  const storage = componentByKey.get("storage_backend") || {};

  els.identityReadiness.className = "identity-readiness";
  els.identityReadiness.innerHTML = `
    <section class="evidence-hero">
      <div>
        <span>Evidence room status</span>
        <strong class="${statusClass}">${escapeHtml(formatPolicyName(payload.status || "review"))}</strong>
        <p>${escapeHtml(payload.limitation || "This is a prototype evidence summary, not a production security certification.")}</p>
      </div>
      <dl>
        <div><dt>Generated</dt><dd>${escapeHtml(payload.generated_at || "-")}</dd></div>
        <div><dt>Blockers</dt><dd>${Number(blockers.length)}</dd></div>
        <div><dt>Warnings</dt><dd>${Number(warnings.length)}</dd></div>
      </dl>
    </section>
    <section class="evidence-summary-grid">
      <div><span>Auth provider</span><strong>${escapeHtml(formatPolicyName(payload.auth_provider_mode || "unknown"))}</strong><em>${escapeHtml(provider.summary || "Provider mode not reported.")}</em></div>
      <div><span>Invite delivery</span><strong>${escapeHtml(formatPolicyName(payload.invite_delivery_mode || "unknown"))}</strong><em>${escapeHtml(invite.summary || "Invite delivery evidence not reported.")}</em></div>
      <div><span>MFA posture</span><strong>${escapeHtml(formatPolicyName(payload.mfa_mode || "unknown"))}</strong><em>${escapeHtml(mfa.summary || "MFA evidence not reported.")}</em></div>
      <div><span>Session controls</span><strong>${escapeHtml(formatPolicyName(payload.session_control_mode || "unknown"))}</strong><em>${escapeHtml(sessions.summary || "Session controls not reported.")}</em></div>
      <div><span>Tenant isolation</span><strong>${escapeHtml(formatPolicyName(payload.tenant_isolation_mode || "unknown"))}</strong><em>${escapeHtml(tenant.summary || "Tenant isolation evidence not reported.")}</em></div>
      <div><span>Storage backend</span><strong>${escapeHtml(formatPolicyName(payload.storage_backend || "unknown"))}</strong><em>${escapeHtml(storage.summary || "Storage evidence not reported.")}</em></div>
    </section>
    <section class="evidence-section">
      <h4>Status evidence</h4>
      <div class="evidence-row-list">${rows || "<p class=\"tiny-text\">No evidence rows returned.</p>"}</div>
    </section>
    <section class="evidence-section">
      <h4>Next controls before real user data</h4>
      <ul class="evidence-next-controls">${nextControls}</ul>
    </section>
  `;
}

async function refreshSecurityReadiness() {
  setPanelState(
    els.identityReadiness,
    "identity-readiness",
    "loading",
    "Loading Security Evidence Room",
    "Collecting identity, invite, MFA, session, tenant, and storage evidence.",
  );
  setPanelState(
    els.securityReadiness,
    "table-shell",
    "loading",
    "Loading security readiness",
    "Checking current pre-pilot security controls.",
  );
  const [readinessResult, identityResult] = await Promise.allSettled([
    apiFetch("/admin/security/readiness"),
    apiFetch("/admin/security/identity-readiness"),
  ]);

  if (readinessResult.status === "fulfilled") {
    renderSecurityReadiness(readinessResult.value);
  } else {
    setPanelState(
      els.securityReadiness,
      "table-shell",
      "error",
      "Security readiness unavailable",
      readinessResult.reason?.message || "The readiness gate could not be loaded.",
    );
  }

  if (identityResult.status === "fulfilled") {
    renderIdentityReadiness(identityResult.value);
  } else {
    setPanelState(
      els.identityReadiness,
      "identity-readiness",
      "error",
      "Security Evidence Room unavailable",
      identityResult.reason?.message || "The identity readiness evidence endpoint could not be loaded.",
    );
  }

  if (readinessResult.status === "rejected" && identityResult.status === "rejected") {
    throw readinessResult.reason;
  }
  return {
    readiness: readinessResult.status === "fulfilled" ? readinessResult.value : null,
    identity_readiness: identityResult.status === "fulfilled" ? identityResult.value : null,
  };
}

async function refreshStaffUsers() {
  const [rows, readiness] = await Promise.all([
    apiFetch("/admin/users"),
    apiFetch("/admin/security/mfa-readiness"),
  ]);
  renderMfaReadiness(readiness);
  renderStaffUsers(rows);
}

function renderMfaReadiness(readiness) {
  if (!els.mfaReadiness) return;
  const statusClass = readiness.status === "blocked" ? "risk-high" : "risk-low";
  els.mfaReadiness.className = "metric-grid mfa-readiness";
  els.mfaReadiness.innerHTML = `
    <div class="metric">
      <span>MFA posture</span>
      <strong class="${statusClass}">${escapeHtml(formatPolicyName(readiness.status))}</strong>
    </div>
    <div class="metric">
      <span>Missing MFA</span>
      <strong>${Number(readiness.missing_mfa_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Attested</span>
      <strong>${Number(readiness.mfa_attested_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Active staff</span>
      <strong>${Number(readiness.active_staff_count || 0)}</strong>
    </div>
    <p class="tiny-text full-width">${escapeHtml(readiness.recommended_action || "Record MFA attestation before pilot use.")}</p>
    <p class="tiny-text full-width">${escapeHtml(readiness.limitation || "MFA Readiness v2 requires a prototype second-factor code for staff sessions.")}</p>
  `;
}

function renderStaffUsers(rows) {
  if (!rows.length) {
    setPanelState(
      els.staffUsers,
      "table-shell",
      "empty",
      "No staff users loaded",
      "Created analyst accounts will appear here.",
    );
    return;
  }
  els.staffUsers.className = "table-shell";
  const body = rows
    .map((user) => {
      const canDisable = user.role === "mfi_analyst" && !user.disabled_at;
      const canReactivate = user.role === "mfi_analyst" && Boolean(user.disabled_at);
      const canAttestMfa = ["admin", "mfi_analyst"].includes(user.role)
        && !user.disabled_at
        && !user.mfa_attested_at;
      const status = user.disabled_at ? "disabled" : "active";
      const mfaStatus = user.mfa_attested_at ? `attested (${user.mfa_method || "method recorded"})` : "missing";
      const actions = [];
      if (canAttestMfa) {
        actions.push(`<button class="secondary-button compact-button" type="button" data-attest-mfa-email="${escapeHtml(user.email)}">Mark MFA</button>`);
      }
      if (canDisable) {
        actions.push(`<button class="secondary-button compact-button" type="button" data-disable-user-email="${escapeHtml(user.email)}">Disable</button>`);
      }
      if (canReactivate) {
        actions.push(`<button class="primary-button compact-button" type="button" data-reactivate-user-email="${escapeHtml(user.email)}">Reactivate</button>`);
      }
      const action = actions.join(" ") || "-";
      return `
        <tr>
          <td>${escapeHtml(user.email)}</td>
          <td>${escapeHtml(formatPolicyName(user.role))}</td>
          <td>${escapeHtml(formatPolicyName(status))}</td>
          <td>${escapeHtml(mfaStatus)}</td>
          <td>${escapeHtml(user.organization_id || "-")}</td>
          <td>${escapeHtml(user.disabled_at || user.created_at || "-")}</td>
          <td>${action}</td>
        </tr>
      `;
    })
    .join("");
  els.staffUsers.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Email</th>
          <th>Role</th>
          <th>Status</th>
          <th>MFA</th>
          <th>Organization</th>
          <th>Created / disabled</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

function renderStaffSessions(rows) {
  if (!rows.length) {
    setPanelState(
      els.staffSessions,
      "table-shell",
      "empty",
      "No active staff sessions",
      "Active admin and analyst sessions will appear here without exposing bearer tokens.",
    );
    return;
  }
  els.staffSessions.className = "table-shell";
  const body = rows
    .map((session) => {
      const actions = session.is_current_session
        ? "Current session"
        : `<button class="secondary-button compact-button" type="button" data-revoke-session-id="${escapeHtml(session.session_id)}">Revoke</button>`;
      return `
        <tr>
          <td>${escapeHtml(session.email)}</td>
          <td>${escapeHtml(formatPolicyName(session.role))}</td>
          <td>${escapeHtml(session.organization_id || "-")}</td>
          <td>${escapeHtml(session.session_expires_at || "-")}</td>
          <td>${escapeHtml(session.session_preview || "-")}</td>
          <td>${actions}</td>
        </tr>
      `;
    })
    .join("");
  els.staffSessions.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Email</th>
          <th>Role</th>
          <th>Organization</th>
          <th>Expires</th>
          <th>Session preview</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

async function refreshStaffSessions() {
  const rows = await apiFetch("/admin/staff-sessions");
  renderStaffSessions(rows);
}

function staffInviteStatus(invite) {
  if (invite.revoked_at) return "revoked";
  if (invite.accepted_at) return "accepted";
  if (invite.expires_at && Date.parse(invite.expires_at) <= Date.now()) return "expired";
  return "pending";
}

function renderStaffInviteDeliveryReadiness(readiness) {
  if (!els.staffInviteDeliveryReadiness) return;
  const statusClass = readiness.status === "blocked"
    ? "risk-high"
    : readiness.status === "review"
      ? "risk-medium"
      : "risk-low";
  const configuredProvider = (readiness.providers || []).find((row) => row.configured) || {};
  const blockerCount = (readiness.production_blockers || []).length;
  const warningCount = (readiness.warnings || []).length;
  const configurationStatus = configuredProvider.configuration_status || "unknown";
  const missingEnvironment = configuredProvider.missing_environment || [];
  const configurationWarnings = configuredProvider.configuration_warnings || [];
  const configurationClass = configuredProvider.configuration_ready
    ? "risk-low"
    : configurationStatus === "not_required"
      ? ""
      : "risk-high";
  els.staffInviteDeliveryReadiness.className = "metric-grid invite-delivery-readiness";
  els.staffInviteDeliveryReadiness.innerHTML = `
    <div class="metric">
      <span>Delivery readiness</span>
      <strong class="${statusClass}">${escapeHtml(formatPolicyName(readiness.status))}</strong>
    </div>
    <div class="metric">
      <span>Configured provider</span>
      <strong>${escapeHtml(formatPolicyName(readiness.configured_provider || "unknown"))}</strong>
    </div>
    <div class="metric">
      <span>Provider mode</span>
      <strong>${escapeHtml(formatPolicyName(configuredProvider.mode || "unknown"))}</strong>
    </div>
    <div class="metric">
      <span>Adapter config</span>
      <strong class="${configurationClass}">${escapeHtml(formatPolicyName(configurationStatus))}</strong>
    </div>
    <div class="metric">
      <span>HTTPS invite URL</span>
      <strong>${readiness.invite_url_https ? "Yes" : "No"}</strong>
    </div>
    <div class="metric">
      <span>Undelivered active</span>
      <strong>${Number(readiness.undelivered_active_invite_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Failed latest attempts</span>
      <strong>${Number(readiness.failed_latest_attempt_count || 0)}</strong>
    </div>
    <p class="tiny-text full-width">
      ${escapeHtml(configuredProvider.summary || readiness.limitation || "Delivery readiness contract not reported.")}
      Blockers: ${Number(blockerCount)}; warnings: ${Number(warningCount)}.
      Missing env: ${missingEnvironment.length ? escapeHtml(missingEnvironment.join(", ")) : "none"}.
      Config warnings: ${configurationWarnings.length ? escapeHtml(configurationWarnings.join(" ")) : "none"}.
      ${escapeHtml(readiness.limitation || "")}
    </p>
  `;
}

function renderStaffInviteHealth(health) {
  if (!els.staffInviteHealth) return;
  const statusClass = health.status === "attention" ? "risk-high" : "risk-low";
  els.staffInviteHealth.className = "metric-grid invite-health";
  els.staffInviteHealth.innerHTML = `
    <div class="metric">
      <span>Status</span>
      <strong class="${statusClass}">${escapeHtml(formatPolicyName(health.status))}</strong>
    </div>
    <div class="metric">
      <span>Action required</span>
      <strong>${Number(health.action_required_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Active pending</span>
      <strong>${Number(health.active_pending_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Expired pending</span>
      <strong>${Number(health.expired_pending_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Expiring ${Number(health.window_hours || 24)}h</span>
      <strong>${Number(health.expiring_soon_count || 0)}</strong>
    </div>
    <div class="metric">
      <span>Closed</span>
      <strong>${Number(health.accepted_count || 0) + Number(health.revoked_count || 0)}</strong>
    </div>
    <p class="tiny-text full-width">${escapeHtml(health.recommended_action || "No pending staff invite rotation action required.")}</p>
  `;
}

function renderStaffInvites(rows) {
  if (!rows.length) {
    setPanelState(
      els.staffInvites,
      "table-shell",
      "empty",
      "No staff invites loaded",
      "Create an expiring invite to onboard an MFI analyst without a temporary password.",
    );
    return;
  }

  els.staffInvites.className = "table-shell";
  const body = rows
    .map((invite) => {
      const status = staffInviteStatus(invite);
      const canRevoke = status === "pending";
      const canRotate = status !== "accepted";
      const canRetryDelivery = (
        canRevoke
        && !invite.delivered_at
        && ["failed", "queued"].includes(invite.last_delivery_status)
      );
      const actions = [];
      if (canRetryDelivery) {
        actions.push(`<button class="secondary-button compact-button" type="button" data-retry-delivery-token="${escapeHtml(invite.token_id)}">Retry delivery</button>`);
      }
      if (canRevoke && !invite.delivered_at) {
        actions.push(`<button class="secondary-button compact-button" type="button" data-deliver-invite-token="${escapeHtml(invite.token_id)}">Mark delivered</button>`);
      }
      if (canRotate) {
        actions.push(`<button class="secondary-button compact-button" type="button" data-rotate-invite-token="${escapeHtml(invite.token_id)}">Rotate</button>`);
      }
      if (canRevoke) {
        actions.push(`<button class="secondary-button compact-button" type="button" data-revoke-invite-token="${escapeHtml(invite.token_id)}">Revoke</button>`);
      }
      const delivery = invite.delivered_at
        ? `${formatPolicyName(invite.delivery_channel || "delivered")} by ${invite.delivered_by || "-"}`
        : "not delivered";
      const deliveryAttempts = Number(invite.delivery_attempt_count || 0);
      const deliverySummary = deliveryAttempts
        ? `${delivery}; ${deliveryAttempts} attempt(s), last ${formatPolicyName(invite.last_delivery_status || "unknown")} via ${invite.last_delivery_provider || "-"}`
        : delivery;
      return `
        <tr>
          <td>${escapeHtml(invite.email)}</td>
          <td>${escapeHtml(formatPolicyName(status))}</td>
          <td>${escapeHtml(invite.organization_id)}</td>
          <td>${escapeHtml(invite.expires_at || "-")}</td>
          <td>${escapeHtml(invite.accepted_at || invite.revoked_at || "-")}</td>
          <td>${escapeHtml(deliverySummary)}</td>
          <td>${escapeHtml(invite.token_preview || invite.token_id || "-")}</td>
          <td>${actions.join(" ") || "-"}</td>
        </tr>
      `;
    })
    .join("");
  els.staffInvites.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Email</th>
          <th>Status</th>
          <th>Organization</th>
          <th>Expires</th>
          <th>Closed</th>
          <th>Delivery</th>
          <th>Token preview</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

async function refreshStaffInvites() {
  const [health, deliveryReadiness, rows] = await Promise.all([
    apiFetch("/admin/staff-invites/health"),
    apiFetch("/admin/staff-invites/delivery-readiness"),
    apiFetch("/admin/staff-invites"),
  ]);
  renderStaffInviteHealth(health);
  renderStaffInviteDeliveryReadiness(deliveryReadiness);
  renderStaffInvites(rows);
}

async function refreshModelStatus() {
  const payload = await apiFetch("/mfi/model-status");
  state.activeModel = payload.active_model || null;
  if (!els.modelStatusPill) return payload;
  if (payload.scoring_allowed && payload.active_model) {
    els.modelStatusPill.className = "pill status-scored";
    els.modelStatusPill.textContent = `Active model: ${payload.active_model.version}`;
    els.modelStatusPill.title = payload.note || "";
  } else {
    els.modelStatusPill.className = "pill status-declined";
    els.modelStatusPill.textContent = "Scoring disabled";
    els.modelStatusPill.title = payload.note || "";
  }
  return payload;
}

function renderModelVersions(rows) {
  if (!rows.length) {
    els.modelVersionRegistry.className = "model-version-grid empty";
    els.modelVersionRegistry.textContent = "No model versions registered.";
    return;
  }
  els.modelVersionRegistry.className = "model-version-grid";
  els.modelVersionRegistry.innerHTML = rows
    .map((model) => {
      const metrics = Object.entries(model.metrics || {})
        .map(([key, value]) => `${formatPolicyName(key)}: ${typeof value === "number" ? value.toFixed(4) : value}`)
        .join(" / ");
      const limitations = (model.limitations || [])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
      const action = model.is_active
        ? `<span class="pill status-approved">Active runtime</span>`
        : `<button class="secondary-button activate-model-button" type="button" data-model-version="${escapeHtml(model.version)}">Activate</button>`;
      return `
        <article class="model-version-card ${model.is_active ? "active-model" : ""}">
          <div class="model-version-heading">
            <div>
              <span>${escapeHtml(formatPolicyName(model.lifecycle_status))}</span>
              <strong>${escapeHtml(model.version)}</strong>
            </div>
            ${action}
          </div>
          <div class="model-version-meta">
            <span>${escapeHtml(model.feature_schema_version)}</span>
            <span>seed ${escapeHtml(model.random_state)}</span>
          </div>
          <strong>${escapeHtml(model.training_data_label)}</strong>
          <span class="tiny-text">${escapeHtml(metrics || "Metrics not recorded")}</span>
          <ul class="model-version-limitations">${limitations}</ul>
        </article>
      `;
    })
    .join("");
}

async function refreshModelVersions() {
  const rows = await apiFetch("/admin/model-versions");
  renderModelVersions(rows);
  return rows;
}

async function createModelVersion(event) {
  event.preventDefault();
  const form = els.modelVersionForm;
  const rocAuc = formNumber(form, "roc_auc");
  const brierScore = formNumber(form, "brier_score");
  const metrics = {};
  if (rocAuc !== undefined) metrics.roc_auc = rocAuc;
  if (brierScore !== undefined) metrics.brier_score = brierScore;
  const created = await apiFetch("/admin/model-versions", {
    method: "POST",
    body: JSON.stringify({
      version: form.elements.version.value.trim(),
      model_name: "Logistic Regression",
      feature_schema_version: form.elements.feature_schema_version.value.trim(),
      training_data_label: form.elements.training_data_label.value.trim(),
      random_state: Number(form.elements.random_state.value),
      metrics,
      limitations: form.elements.limitations.value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    }),
  });
  form.elements.version.value = "";
  await Promise.all([refreshModelVersions(), refreshAudit()]);
  showMessage(`Registered model candidate ${created.version}`, "ok");
}

async function activateModelVersion(version) {
  const activated = await apiFetch(
    `/admin/model-versions/${encodeURIComponent(version)}/activate`,
    { method: "POST" },
  );
  await Promise.all([refreshModelVersions(), refreshModelStatus(), refreshAudit()]);
  showMessage(`Activated model ${activated.version}; older scores now require review`, "ok");
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
  syncOrganizationSelect(els.staffInviteOrganization, organizations);
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
  els.staffInviteOrganization.value = created.id;
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
  await Promise.all([refreshStaffUsers(), refreshSecurityReadiness(), refreshAudit()]);
}

async function disableStaffUser(email) {
  const disabled = await apiFetch(`/admin/users/${encodeURIComponent(email)}/disable`, {
    method: "POST",
  });
  await Promise.all([refreshStaffUsers(), refreshStaffSessions(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(
    `Disabled ${disabled.email}; revoked ${disabled.revoked_session_count} active session(s).`,
    "ok",
  );
}

async function reactivateStaffUser(email) {
  const reactivated = await apiFetch(`/admin/users/${encodeURIComponent(email)}/reactivate`, {
    method: "POST",
  });
  await Promise.all([refreshStaffUsers(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Reactivated ${reactivated.email}; analyst can sign in again.`, "ok");
}

async function attestStaffMfa(email) {
  const attested = await apiFetch(`/admin/users/${encodeURIComponent(email)}/mfa/attest`, {
    method: "POST",
    body: JSON.stringify({ method: "pilot_attestation" }),
  });
  await Promise.all([refreshStaffUsers(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Recorded MFA attestation for ${attested.email}.`, "ok");
}

async function revokeStaffSession(sessionId) {
  const revoked = await apiFetch(`/admin/staff-sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  await Promise.all([refreshStaffSessions(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Revoked staff session for ${revoked.email}.`, "ok");
}

async function createStaffInvite(event) {
  event.preventDefault();
  const form = els.staffInviteForm;
  const created = await apiFetch("/admin/staff-invites", {
    method: "POST",
    body: JSON.stringify({
      email: form.elements.email.value.trim(),
      role: "mfi_analyst",
      organization_id: form.elements.organization_id.value,
      expires_in_hours: Number(form.elements.expires_in_hours.value || 48),
      queue_delivery: Boolean(form.elements.queue_delivery?.checked),
      delivery_channel: "email",
      delivery_recipient: form.elements.email.value.trim(),
    }),
  });
  form.reset();
  form.elements.expires_in_hours.value = "48";
  const deliveryNote = created.delivery_attempt
    ? ` Local delivery attempt ${created.delivery_attempt.status} via ${created.delivery_attempt.provider}.`
    : "";
  showMessage(`Created invite for ${created.email}. Copy this one-time URL now: ${created.invite_url || created.token}.${deliveryNote}`, "ok");
  await Promise.all([refreshStaffInvites(), refreshSecurityReadiness(), refreshAudit()]);
}

async function markStaffInviteDelivered(token) {
  const delivered = await apiFetch(`/admin/staff-invites/${encodeURIComponent(token)}/delivery`, {
    method: "POST",
    body: JSON.stringify({ channel: "manual_copy" }),
  });
  await Promise.all([refreshStaffInvites(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Recorded invite delivery for ${delivered.email}`, "ok");
}

async function retryStaffInviteDelivery(token) {
  const retried = await apiFetch(`/admin/staff-invites/${encodeURIComponent(token)}/delivery-attempts/retry`, {
    method: "POST",
    body: JSON.stringify({ channel: "email" }),
  });
  const attempt = retried.delivery_attempt || {};
  await Promise.all([refreshStaffInvites(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Retried invite delivery for ${retried.email}: ${attempt.status || "queued"} via ${attempt.provider || "local_outbox"}.`, "ok");
}

async function rotateStaffInvite(token) {
  const rotated = await apiFetch(`/admin/staff-invites/${encodeURIComponent(token)}/rotate`, {
    method: "POST",
    body: JSON.stringify({ expires_in_hours: 48 }),
  });
  await Promise.all([refreshStaffInvites(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Rotated invite for ${rotated.email}. Copy this new one-time URL now: ${rotated.invite_url || rotated.token}`, "ok");
}

async function revokeStaffInvite(token) {
  const revoked = await apiFetch(`/admin/staff-invites/${encodeURIComponent(token)}`, {
    method: "DELETE",
  });
  await Promise.all([refreshStaffInvites(), refreshSecurityReadiness(), refreshAudit()]);
  showMessage(`Revoked invite for ${revoked.email}`, "ok");
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
    renderApplicationValidation([]);
  });
  els.applicationForm.addEventListener("submit", (event) => {
    submitApplication(event).catch((error) => showMessage(error.message, "error"));
  });
  ["input", "change"].forEach((eventName) => {
    els.applicationForm.addEventListener(eventName, (event) => {
      const fieldName = event.target?.name;
      if (!fieldName) return;
      if (fieldName === "district") {
        const expected = window.MicroScoreApplicationIntake?.DISTRICT_SETTLEMENT_TYPES[event.target.value];
        if (expected) els.applicationForm.elements.settlement_type.value = expected;
        clearApplicationFieldValidation("settlement_type");
      }
      clearApplicationFieldValidation(fieldName);
    });
  });
  els.refreshBorrowerApplication.addEventListener("click", () => {
    withButtonBusy(els.refreshBorrowerApplication, "Refreshing...", () => refreshBorrowerApplications())
      .catch((error) => showMessage(error.message, "error"));
  });
  els.borrowerApplicationHistory.addEventListener("click", (event) => {
    const button = event.target.closest("[data-borrower-application-id]");
    if (!button) return;
    openBorrowerApplication(button.dataset.borrowerApplicationId)
      .catch((error) => showMessage(error.message, "error"));
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
  els.simulationForm.addEventListener("submit", (event) => {
    event.preventDefault();
    withButtonBusy(els.runSimulation, "Simulating...", () => runPortfolioSimulation())
      .catch((error) => showMessage(error.message, "error"));
  });
  els.refreshSimulationHistory.addEventListener("click", () => {
    withButtonBusy(els.refreshSimulationHistory, "Refreshing...", () => refreshSimulationHistory())
      .catch((error) => showMessage(error.message, "error"));
  });
  els.simulationHistory.addEventListener("click", (event) => {
    const button = event.target.closest("[data-simulation-id]");
    if (!button) return;
    loadStoredSimulation(button.dataset.simulationId)
      .catch((error) => showMessage(error.message, "error"));
  });
  els.refreshAudit.addEventListener("click", () => {
    refreshAudit().catch((error) => showMessage(error.message, "error"));
  });
  els.refreshUsers.addEventListener("click", () => {
    refreshStaffUsers().catch((error) => showMessage(error.message, "error"));
  });
  els.staffUsers.addEventListener("click", (event) => {
    const mfaButton = event.target.closest("[data-attest-mfa-email]");
    if (mfaButton) {
      attestStaffMfa(mfaButton.dataset.attestMfaEmail)
        .catch((error) => showMessage(error.message, "error"));
      return;
    }
    const disableButton = event.target.closest("[data-disable-user-email]");
    if (disableButton) {
      disableStaffUser(disableButton.dataset.disableUserEmail)
        .catch((error) => showMessage(error.message, "error"));
      return;
    }
    const reactivateButton = event.target.closest("[data-reactivate-user-email]");
    if (!reactivateButton) return;
    reactivateStaffUser(reactivateButton.dataset.reactivateUserEmail)
      .catch((error) => showMessage(error.message, "error"));
  });
  els.refreshStaffSessions.addEventListener("click", () => {
    refreshStaffSessions().catch((error) => showMessage(error.message, "error"));
  });
  els.staffSessions.addEventListener("click", (event) => {
    const revokeSessionButton = event.target.closest("[data-revoke-session-id]");
    if (!revokeSessionButton) return;
    revokeStaffSession(revokeSessionButton.dataset.revokeSessionId)
      .catch((error) => showMessage(error.message, "error"));
  });
  els.refreshStaffInvites.addEventListener("click", () => {
    refreshStaffInvites().catch((error) => showMessage(error.message, "error"));
  });
  els.staffInvites.addEventListener("click", (event) => {
    const retryDeliveryButton = event.target.closest("[data-retry-delivery-token]");
    if (retryDeliveryButton) {
      retryStaffInviteDelivery(retryDeliveryButton.dataset.retryDeliveryToken)
        .catch((error) => showMessage(error.message, "error"));
      return;
    }
    const deliverButton = event.target.closest("[data-deliver-invite-token]");
    if (deliverButton) {
      markStaffInviteDelivered(deliverButton.dataset.deliverInviteToken)
        .catch((error) => showMessage(error.message, "error"));
      return;
    }
    const rotateButton = event.target.closest("[data-rotate-invite-token]");
    if (rotateButton) {
      rotateStaffInvite(rotateButton.dataset.rotateInviteToken)
        .catch((error) => showMessage(error.message, "error"));
      return;
    }
    const revokeButton = event.target.closest("[data-revoke-invite-token]");
    if (!revokeButton) return;
    revokeStaffInvite(revokeButton.dataset.revokeInviteToken)
      .catch((error) => showMessage(error.message, "error"));
  });
  els.refreshModelVersions.addEventListener("click", () => {
    refreshModelVersions().catch((error) => showMessage(error.message, "error"));
  });
  els.modelVersionForm.addEventListener("submit", (event) => {
    createModelVersion(event).catch((error) => showMessage(error.message, "error"));
  });
  els.modelVersionRegistry.addEventListener("click", (event) => {
    const button = event.target.closest("[data-model-version]");
    if (!button) return;
    activateModelVersion(button.dataset.modelVersion)
      .catch((error) => showMessage(error.message, "error"));
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
  els.staffInviteForm.addEventListener("submit", (event) => {
    createStaffInvite(event).catch((error) => showMessage(error.message, "error"));
  });
  els.clearApplications.addEventListener("click", () => {
    clearApplications().catch((error) => showMessage(error.message, "error"));
  });
}

function restoreState() {
  applyRoute();
  fillApplicationForm(demoApplication);
}

wireEvents();
restoreState();
checkApiAndOrganizations().catch((error) => showMessage(error.message, "error"));
