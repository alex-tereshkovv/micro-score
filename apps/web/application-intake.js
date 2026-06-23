(function registerApplicationIntake(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.MicroScoreApplicationIntake = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function buildApplicationIntake() {
  "use strict";

  const DISTRICT_SETTLEMENT_TYPES = Object.freeze({
    "Pavlodar city": "urban",
    Ekibastuz: "industrial_city",
    Aksu: "industrial_city",
    "Pavlodar district": "peri_urban",
    Bayanaul: "rural",
    Sharbakty: "rural",
    Terenkol: "rural",
    Irtysh: "rural",
    Zhelezinka: "rural",
    Aktogay: "rural",
    Akkuly: "rural",
    Uspenka: "rural",
    "May district": "rural",
  });

  const SIGNAL_RULES = Object.freeze({
    annual_income: { label: "Annual income", max: 10_000_000_000 },
    total_outstanding_debt: { label: "Outstanding debt", max: 10_000_000_000 },
    mobile_banking_logins: { label: "Mobile logins", max: 10_000, integer: true },
    online_transfer_frequency: { label: "Online transfers", max: 10_000, integer: true },
    atm_withdrawal_frequency: { label: "ATM withdrawals", max: 10_000, integer: true },
    avg_deposit_amount: { label: "Average deposits", max: 10_000_000_000 },
    debit_card_spending: { label: "Card spending", max: 10_000_000_000 },
    num_open_loans: { label: "Open loans", max: 100, integer: true },
    late_payment_count: { label: "Late payments", max: 1_000, integer: true },
  });

  const TOP_LEVEL_FIELDS = new Set([
    "requested_amount",
    "purpose",
    "district",
    "settlement_type",
    "organization_id",
    "consent_confirmed",
    "consent_version",
    "behavioral_signals",
  ]);
  const GENDERS = new Set(["Female", "Male", "Other"]);
  const EMPLOYMENT_STATUSES = new Set(["Self-employed", "Employed", "Unemployed"]);

  function addError(errors, field, message) {
    errors.push({ field, message });
  }

  function optionalNumber(errors, signals, field, rule) {
    const raw = signals[field];
    if (raw === undefined || raw === null || raw === "") return;
    const value = typeof raw === "number" ? raw : Number(raw);
    if (!Number.isFinite(value)) {
      addError(errors, `behavioral_signals.${field}`, `${rule.label} must be a number.`);
      return;
    }
    if (value < 0 || value > rule.max) {
      addError(
        errors,
        `behavioral_signals.${field}`,
        `${rule.label} must be between 0 and ${rule.max.toLocaleString("en-US")}.`,
      );
    } else if (rule.integer && !Number.isInteger(value)) {
      addError(errors, `behavioral_signals.${field}`, `${rule.label} must be a whole number.`);
    }
  }

  function validateApplicationIntake(payload) {
    const errors = [];
    const body = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
    Object.keys(body).forEach((field) => {
      if (!TOP_LEVEL_FIELDS.has(field)) addError(errors, field, `Unexpected field: ${field}.`);
    });

    const requestedAmount = Number(body.requested_amount);
    if (!Number.isFinite(requestedAmount) || requestedAmount < 1_000 || requestedAmount > 100_000_000) {
      addError(errors, "requested_amount", "Requested amount must be between 1,000 and 100,000,000.");
    }
    if (!String(body.organization_id || "").trim()) {
      addError(errors, "organization_id", "Select an MFI organization.");
    }
    if (String(body.purpose || "").trim().length > 200) {
      addError(errors, "purpose", "Purpose must be 200 characters or fewer.");
    }

    const expectedSettlement = DISTRICT_SETTLEMENT_TYPES[body.district];
    if (body.district && !expectedSettlement) {
      addError(errors, "district", "Select a supported Pavlodar district.");
    }
    if (body.settlement_type && !new Set(Object.values(DISTRICT_SETTLEMENT_TYPES)).has(body.settlement_type)) {
      addError(errors, "settlement_type", "Select a supported settlement type.");
    } else if (expectedSettlement && body.settlement_type !== expectedSettlement) {
      addError(
        errors,
        "settlement_type",
        `Settlement type for ${body.district} must be ${expectedSettlement}.`,
      );
    }

    if (body.consent_confirmed !== true) {
      addError(errors, "borrower_consent", "Confirm synthetic-data consent before submitting.");
    }
    if (!String(body.consent_version || "").trim()) {
      addError(errors, "consent_version", "Consent version is required for auditability.");
    }

    const signals = body.behavioral_signals;
    if (!signals || typeof signals !== "object" || Array.isArray(signals)) {
      addError(errors, "behavioral_signals", "Behavioral signals must be an object.");
    } else {
      const allowedSignals = new Set([
        ...Object.keys(SIGNAL_RULES),
        "gender",
        "employment_status",
      ]);
      Object.keys(signals).forEach((field) => {
        if (!allowedSignals.has(field)) {
          addError(errors, `behavioral_signals.${field}`, `Unexpected behavioral field: ${field}.`);
        }
      });
      Object.entries(SIGNAL_RULES).forEach(([field, rule]) => {
        optionalNumber(errors, signals, field, rule);
      });
      if (signals.gender !== undefined && signals.gender !== null && !GENDERS.has(signals.gender)) {
        addError(errors, "behavioral_signals.gender", "Select a supported gender value.");
      }
      if (
        signals.employment_status !== undefined
        && signals.employment_status !== null
        && !EMPLOYMENT_STATUSES.has(signals.employment_status)
      ) {
        addError(errors, "behavioral_signals.employment_status", "Select a supported employment status.");
      }
    }

    return { valid: errors.length === 0, errors };
  }

  function formatApplicationIntakeErrors(errors) {
    return (errors || []).map((error) => error.message).join(" ");
  }

  return {
    DISTRICT_SETTLEMENT_TYPES,
    SIGNAL_RULES,
    formatApplicationIntakeErrors,
    validateApplicationIntake,
  };
});
