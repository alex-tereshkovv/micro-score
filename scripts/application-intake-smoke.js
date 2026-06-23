const {
  DISTRICT_SETTLEMENT_TYPES,
  validateApplicationIntake,
} = require("../apps/web/application-intake.js");

function validPayload() {
  return {
    requested_amount: 300_000,
    purpose: "working capital",
    district: "Pavlodar city",
    settlement_type: "urban",
    organization_id: "pavlodar-demo-mfi",
    consent_confirmed: true,
    consent_version: "synthetic-demo-v1",
    behavioral_signals: {
      annual_income: 4_200_000,
      total_outstanding_debt: 650_000,
      mobile_banking_logins: 18,
      online_transfer_frequency: 7,
      atm_withdrawal_frequency: 2,
      avg_deposit_amount: 140_000,
      debit_card_spending: 90_000,
      num_open_loans: 1,
      late_payment_count: 0,
      gender: "Female",
      employment_status: "Self-employed",
    },
  };
}

function expectInvalid(payload, field) {
  const result = validateApplicationIntake(payload);
  if (result.valid || !result.errors.some((error) => error.field === field)) {
    throw new Error(`Expected ${field} validation error: ${JSON.stringify(result)}`);
  }
  return result.errors.length;
}

const accepted = validateApplicationIntake(validPayload());
if (!accepted.valid) throw new Error(`Expected valid intake: ${JSON.stringify(accepted.errors)}`);

const amountErrors = expectInvalid({ ...validPayload(), requested_amount: 999 }, "requested_amount");
const settlementErrors = expectInvalid(
  { ...validPayload(), district: "Aksu", settlement_type: "urban" },
  "settlement_type",
);
const countErrors = expectInvalid(
  {
    ...validPayload(),
    behavioral_signals: { ...validPayload().behavioral_signals, num_open_loans: 1.5 },
  },
  "behavioral_signals.num_open_loans",
);
const unknownErrors = expectInvalid(
  {
    ...validPayload(),
    behavioral_signals: { ...validPayload().behavioral_signals, unreviewed_proxy: 1 },
  },
  "behavioral_signals.unreviewed_proxy",
);
const consentErrors = expectInvalid(
  { ...validPayload(), consent_confirmed: false },
  "borrower_consent",
);

process.stdout.write(`${JSON.stringify({
  mode: "application-intake-smoke",
  accepted: accepted.valid,
  district_rules: Object.keys(DISTRICT_SETTLEMENT_TYPES).length,
  rejected_cases: 5,
  validation_errors: amountErrors + settlementErrors + countErrors + unknownErrors + consentErrors,
})}\n`);
