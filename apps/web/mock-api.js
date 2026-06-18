(() => {
  const demo = {
    users: {},
    organizations: {},
    sessions: {},
    applications: [],
    timelines: {},
    auditEvents: [],
    nextTimelineId: 1,
    nextAuditId: 1,
    nextDecisionId: 1,
    nextApplicationNumber: 1,
  };

  const demoUsers = [
    ["borrower@test.com", "borrower", null],
    ["analyst@test.com", "mfi_analyst", "pavlodar-demo-mfi"],
    ["admin@test.com", "admin", null],
  ];

  const commonPasswords = new Set([
    "1234567890",
    "admin123",
    "letmein123",
    "password",
    "password123",
    "qwerty123",
  ]);

  function passwordPolicyViolations(password) {
    const value = String(password || "");
    const violations = [];
    if (value.length < 10) violations.push("use at least 10 characters");
    if (!/[a-z]/.test(value)) violations.push("include a lowercase letter");
    if (!/[A-Z]/.test(value)) violations.push("include an uppercase letter");
    if (!/[0-9]/.test(value)) violations.push("include a number");
    if (/^[a-z0-9]+$/i.test(value)) violations.push("include a symbol");
    if (commonPasswords.has(value.trim().toLowerCase())) violations.push("avoid a common password");
    return violations;
  }

  const forbiddenSignalTokens = new Set([
    "address",
    "biometric",
    "email",
    "iin",
    "latitude",
    "longitude",
    "passport",
    "phone",
    "photo",
    "voice",
  ]);
  const forbiddenSignalPhrases = [
    "bank_statement",
    "device_fingerprint",
    "first_name",
    "full_name",
    "id_number",
    "last_name",
    "national_id",
    "phone_book",
    "precise_geolocation",
    "raw_transaction",
    "social_media",
    "transaction_description",
    "voice_recording",
  ];

  function normalizedSignalKey(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function signalKeyIsForbidden(key) {
    const normalized = normalizedSignalKey(key);
    const tokens = normalized.split("_");
    return (
      tokens.some((token) => forbiddenSignalTokens.has(token)) ||
      forbiddenSignalPhrases.some((phrase) => normalized.includes(phrase))
    );
  }

  function findForbiddenSignalPaths(value, path = "behavioral_signals") {
    const matches = [];
    if (Array.isArray(value)) {
      value.forEach((child, index) => {
        matches.push(...findForbiddenSignalPaths(child, `${path}[${index}]`));
      });
    } else if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, child]) => {
        const childPath = `${path}.${key}`;
        if (signalKeyIsForbidden(key)) matches.push(childPath);
        matches.push(...findForbiddenSignalPaths(child, childPath));
      });
    }
    return [...new Set(matches)].sort();
  }

  function validateApplicationPrivacy(payload) {
    if (payload.consent_confirmed !== true) {
      throw new Error("Confirm synthetic-data consent before submitting an application");
    }
    if (!String(payload.consent_version || "").trim()) {
      throw new Error("A consent version is required for auditability");
    }
    const forbiddenPaths = findForbiddenSignalPaths(payload.behavioral_signals || {});
    if (forbiddenPaths.length) {
      throw new Error(`Remove sensitive personal fields: ${forbiddenPaths.join(", ")}`);
    }
  }

  const seedApplications = [
    {
      borrower_email: "borrower@test.com",
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
      decision: "approve",
      decision_note: "Starter loan approved with standard follow-up.",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 4200,
      purpose: "farm equipment repair",
      district: "Bayanaul",
      settlement_type: "rural",
      annual_income: 38000,
      total_outstanding_debt: 9700,
      mobile_banking_logins: 8,
      online_transfer_frequency: 3,
      atm_withdrawal_frequency: 5,
      avg_deposit_amount: 900,
      debit_card_spending: 680,
      num_open_loans: 2,
      late_payment_count: 1,
      gender: "Male",
      employment_status: "Self-employed",
      decision: "review",
      decision_note: "Request income context before final decision.",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 2500,
      purpose: "household inventory",
      district: "Ekibastuz",
      settlement_type: "industrial_city",
      annual_income: 47000,
      total_outstanding_debt: 5400,
      mobile_banking_logins: 22,
      online_transfer_frequency: 11,
      atm_withdrawal_frequency: 1,
      avg_deposit_amount: 1600,
      debit_card_spending: 1100,
      num_open_loans: 1,
      late_payment_count: 0,
      gender: "Female",
      employment_status: "Employed",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 6100,
      purpose: "seasonal inventory",
      district: "Akkuly",
      settlement_type: "rural",
      annual_income: 31000,
      total_outstanding_debt: 14200,
      mobile_banking_logins: 4,
      online_transfer_frequency: 1,
      atm_withdrawal_frequency: 7,
      avg_deposit_amount: 450,
      debit_card_spending: 420,
      num_open_loans: 3,
      late_payment_count: 2,
      gender: "Male",
      employment_status: "Self-employed",
      decision: "decline",
      decision_note: "Debt load and recent payment history require a smaller offer.",
    },
    {
      borrower_email: "borrower@test.com",
      requested_amount: 1800,
      purpose: "education fees",
      district: "Aksu",
      settlement_type: "urban",
      annual_income: 44000,
      total_outstanding_debt: 3100,
      mobile_banking_logins: 15,
      online_transfer_frequency: 6,
      atm_withdrawal_frequency: 2,
      avg_deposit_amount: 1200,
      debit_card_spending: 760,
      num_open_loans: 0,
      late_payment_count: 0,
      gender: "Female",
      employment_status: "Employed",
      decision: "approve",
      decision_note: "Low debt burden and active digital behavior.",
    },
  ];

  function nowIso() {
    return new Date().toISOString();
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function parseBody(options) {
    if (!options?.body) return {};
    return typeof options.body === "string" ? JSON.parse(options.body) : options.body;
  }

  function resetDemo() {
    demo.users = {};
    demo.organizations = {
      "pavlodar-demo-mfi": {
        id: "pavlodar-demo-mfi",
        name: "Pavlodar Demo MFI",
        region: "Pavlodar region, Kazakhstan",
        created_at: nowIso(),
      },
    };
    demo.applications = [];
    demo.timelines = {};
    demo.auditEvents = [];
    demo.nextTimelineId = 1;
    demo.nextAuditId = 1;
    demo.nextDecisionId = 1;
    demo.nextApplicationNumber = 1;

    demoUsers.forEach(([email, role, organizationId]) => {
      demo.users[email] = {
        email,
        role,
        organization_id: organizationId,
        password: "password123",
        created_at: nowIso(),
      };
    });

    seedApplications.forEach((seed, index) => {
      const app = createApplicationRecord(seed, seed.borrower_email, `static-demo-${index + 1}`);
      app.score_result = buildScore(app);
      app.status = "scored";
      app.scored_at = nowIso();
      addTimeline(app.id, "application_scored", "analyst@test.com", {
        model_version: app.score_result.model_version,
        risk_band: app.score_result.risk_band,
      });
      if (seed.decision) {
        app.decision_result = createDecision(app.id, "analyst@test.com", {
          decision: seed.decision,
          policy_name: "balanced_review",
          note: seed.decision_note || "",
        });
        addTimeline(app.id, "application_decision_recorded", "analyst@test.com", {
          decision: seed.decision,
          policy_name: "balanced_review",
        });
      }
      demo.applications.push(app);
    });
  }

  function createApplicationRecord(payload, borrowerEmail, id = null) {
    const behavioral = { ...(payload.behavioral_signals || {}) };
    [
      "annual_income",
      "total_outstanding_debt",
      "mobile_banking_logins",
      "online_transfer_frequency",
      "atm_withdrawal_frequency",
      "avg_deposit_amount",
      "debit_card_spending",
      "num_open_loans",
      "late_payment_count",
      "gender",
      "employment_status",
    ].forEach((key) => {
      if (payload[key] !== undefined) behavioral[key] = payload[key];
    });

    behavioral.loan_application_amount = payload.requested_amount;
    if (payload.district) behavioral.pavlodar_district = payload.district;
    if (payload.settlement_type) behavioral.settlement_type = payload.settlement_type;

    const application = {
      id: id || `static-demo-new-${demo.nextApplicationNumber++}`,
      borrower_email: borrowerEmail,
      status: "submitted",
      requested_amount: payload.requested_amount,
      purpose: payload.purpose || "",
      district: payload.district || null,
      settlement_type: payload.settlement_type || null,
      organization_id: payload.organization_id || "pavlodar-demo-mfi",
      behavioral_signals: behavioral,
      score_result: null,
      decision_result: null,
      created_at: nowIso(),
      scored_at: null,
    };
    demo.timelines[application.id] = [];
    addTimeline(application.id, "application_created", borrowerEmail, {
      requested_amount: payload.requested_amount,
      district: payload.district || "unknown",
    });
    return application;
  }

  function addTimeline(applicationId, action, actorEmail, details = {}) {
    const event = {
      id: demo.nextTimelineId++,
      action,
      title: timelineTitle(action),
      actor_email: actorEmail,
      details,
      created_at: nowIso(),
    };
    demo.timelines[applicationId] = demo.timelines[applicationId] || [];
    demo.timelines[applicationId].push(event);
    return event;
  }

  function addAudit(action, entityType, entityId, actorEmail, details = {}) {
    const event = {
      id: demo.nextAuditId++,
      actor_email: actorEmail,
      action,
      entity_type: entityType,
      entity_id: entityId,
      details,
      created_at: nowIso(),
    };
    demo.auditEvents.unshift(event);
    return event;
  }

  function timelineTitle(action) {
    const titles = {
      application_created: "Application submitted",
      application_scored: "Risk score generated",
      application_decision_recorded: "Analyst decision recorded",
    };
    return titles[action] || action.replaceAll("_", " ");
  }

  function riskBand(probability) {
    if (probability >= 0.58) return "high";
    if (probability >= 0.34) return "medium";
    return "low";
  }

  function factor(feature, value, direction, label = null) {
    return {
      feature,
      value,
      abs_value: Math.abs(value),
      direction,
      label: label || feature,
    };
  }

  function buildScore(application) {
    const s = application.behavioral_signals || {};
    const income = number(s.annual_income, 1);
    const debt = number(s.total_outstanding_debt);
    const late = number(s.late_payment_count);
    const openLoans = number(s.num_open_loans);
    const digitalActivity = number(s.mobile_banking_logins) + number(s.online_transfer_frequency);
    const debtRatio = income ? debt / income : 0.5;
    const ruralRisk = application.settlement_type === "rural" ? 0.06 : 0;
    const districtRisk = ["Akkuly", "Bayanaul", "Uspenka", "Zhelezinka"].includes(application.district) ? 0.04 : 0;
    const digitalProtection = clamp(digitalActivity / 120, 0, 0.18);
    const probability = clamp(
      0.22 + late * 0.16 + debtRatio * 0.48 + openLoans * 0.035 + ruralRisk + districtRisk - digitalProtection,
      0.04,
      0.92,
    );
    const proxyDelta = clamp(late * 0.11, 0, 0.38);
    const thinFileProbability = clamp(probability - proxyDelta + 0.03, 0.04, 0.92);
    const regionalNeutralProbability = clamp(probability - ruralRisk - districtRisk, 0.04, 0.92);
    const band = riskBand(probability);

    const positiveFactors = [
      factor("late_payment_count", late * 0.48, "raises_risk", "Late payments"),
      factor("debt_to_income_ratio", debtRatio * 0.42, "raises_risk", "Debt to income"),
      factor("num_open_loans", openLoans * 0.08, "raises_risk", "Open loans"),
      factor("regional_access_context", ruralRisk + districtRisk, "raises_risk", "Regional access context"),
    ].filter((item) => item.value > 0);
    const protectiveFactors = [
      factor("mobile_banking_logins", -number(s.mobile_banking_logins) * 0.012, "lowers_risk", "Mobile banking use"),
      factor("online_transfer_frequency", -number(s.online_transfer_frequency) * 0.014, "lowers_risk", "Online transfers"),
      factor("avg_deposit_amount", -clamp(number(s.avg_deposit_amount) / 10000, 0, 0.22), "lowers_risk", "Average deposits"),
    ].filter((item) => item.value < 0);

    return {
      model_name: "static-demo-scorecard",
      model_version: "static-demo-v1",
      high_risk_probability: probability,
      risk_band: band,
      proxy_sensitivity_delta: proxyDelta,
      scenario_scores: [
        {
          scenario: "full_feature_demo",
          label: "Standard demo score",
          high_risk_probability: probability,
          risk_band: band,
          notes: ["Uses synthetic demo features."],
        },
        {
          scenario: "thin_file_without_late_payment_count",
          label: "Thin-file stress test",
          high_risk_probability: thinFileProbability,
          risk_band: riskBand(thinFileProbability),
          notes: ["Removes the strongest proxy-style signal."],
        },
        {
          scenario: "regional_neutral",
          label: "Regional neutral check",
          high_risk_probability: regionalNeutralProbability,
          risk_band: riskBand(regionalNeutralProbability),
          notes: ["Removes regional access assumptions."],
        },
      ],
      decision_support: decisionSupport(probability, proxyDelta, band),
      missing_feature_count: 0,
      missing_features_preview: [],
      explanation: {
        method: "static demo additive scorecard",
        baseline_log_odds: 0,
        total_contribution: probability - 0.22,
        predicted_log_odds: probability,
        high_risk_probability: probability,
        top_positive_factors: positiveFactors.slice(0, 4),
        top_protective_factors: protectiveFactors.slice(0, 4),
        top_factors: [...positiveFactors, ...protectiveFactors]
          .sort((left, right) => right.abs_value - left.abs_value)
          .slice(0, 6),
      },
      top_model_factors: [...positiveFactors, ...protectiveFactors]
        .sort((left, right) => right.abs_value - left.abs_value)
        .slice(0, 6),
      warnings: [
        "Static demo mode uses synthetic data only.",
        "late_payment_count is treated as a proxy-sensitive signal in this demo.",
      ],
    };
  }

  function decisionSupport(probability, proxyDelta, band) {
    if (proxyDelta >= 0.2) {
      return {
        recommendation_code: "manual_review_proxy_sensitive",
        title: "Manual review before decision",
        rationale: ["Risk estimate is sensitive to late-payment history.", "Avoid automatic decline from one proxy-heavy signal."],
        next_steps: ["Ask for payment context.", "Check affordability and income stability."],
      };
    }
    if (band === "high") {
      return {
        recommendation_code: "manual_review_high_risk",
        title: "Senior review recommended",
        rationale: ["Predicted risk is high in the demo scorecard."],
        next_steps: ["Consider smaller starter loan.", "Request additional repayment evidence."],
      };
    }
    if (probability <= 0.25) {
      return {
        recommendation_code: "starter_loan_eligible",
        title: "Starter loan candidate",
        rationale: ["Low demo risk estimate and visible digital activity."],
        next_steps: ["Verify identity.", "Offer conservative first limit."],
      };
    }
    return {
      recommendation_code: "balanced_manual_review",
      title: "Balanced manual review",
      rationale: ["Risk is not low enough for automatic approval in the demo."],
      next_steps: ["Review income, debt load, and purpose.", "Record a human decision."],
    };
  }

  function createDecision(applicationId, actorEmail, payload) {
    return {
      id: demo.nextDecisionId++,
      application_id: applicationId,
      actor_email: actorEmail,
      decision: payload.decision,
      policy_name: payload.policy_name || "balanced_review",
      note: payload.note || "",
      created_at: nowIso(),
    };
  }

  function currentUser(session) {
    const sessionEmail = session?.token ? demo.sessions[session.token] : null;
    const user = sessionEmail ? demo.users[sessionEmail] : null;
    if (!user || user.email !== session?.email || user.role !== session?.role) {
      throw new Error("Demo session expired. Sign in again.");
    }
    return {
      email: user.email,
      role: user.role,
      organization_id: user.organization_id || null,
    };
  }

  function requireMfi(session) {
    const user = currentUser(session);
    if (!["mfi_analyst", "admin"].includes(user.role)) throw new Error("MFI access required");
    return user;
  }

  function requireAdmin(session) {
    const user = currentUser(session);
    if (user.role !== "admin") throw new Error("Admin access required");
    return user;
  }

  function findApplication(applicationId) {
    const app = demo.applications.find((item) => item.id === applicationId);
    if (!app) throw new Error("Application not found");
    return app;
  }

  function mfiApplications(user) {
    if (user.role === "admin") return demo.applications;
    if (!user.organization_id) throw new Error("MFI analyst is not assigned to an organization");
    return demo.applications.filter((app) => app.organization_id === user.organization_id);
  }

  function mfiApplication(applicationId, user) {
    const app = findApplication(applicationId);
    if (user.role !== "admin" && app.organization_id !== user.organization_id) {
      throw new Error("Not allowed");
    }
    return app;
  }

  function visibleApplication(applicationId, session) {
    const user = currentUser(session);
    const app = findApplication(applicationId);
    const canReview = user.role === "admin" || (
      user.role === "mfi_analyst" && app.organization_id === user.organization_id
    );
    if (app.borrower_email !== user.email && !canReview) {
      throw new Error("Not allowed");
    }
    return app;
  }

  function reviewPacket(application) {
    const score = application.score_result;
    const flags = governanceFlags(application);
    return {
      application_id: application.id,
      generated_at: nowIso(),
      application: {
        id: application.id,
        borrower_email: application.borrower_email,
        status: application.status,
        requested_amount: application.requested_amount,
        purpose: application.purpose,
        district: application.district,
        settlement_type: application.settlement_type,
        organization_id: application.organization_id,
        created_at: application.created_at,
        scored_at: application.scored_at,
      },
      model_summary: score
        ? {
            model_name: score.model_name,
            model_version: score.model_version,
            risk_band: score.risk_band,
            high_risk_probability: score.high_risk_probability,
            proxy_sensitivity_delta: score.proxy_sensitivity_delta,
            missing_feature_count: score.missing_feature_count,
          }
        : null,
      decision_support: score?.decision_support || null,
      analyst_decision: application.decision_result,
      timeline_events: demo.timelines[application.id] || [],
      scenario_scores: score?.scenario_scores || [],
      top_risk_factors: score?.explanation?.top_positive_factors || [],
      top_protective_factors: score?.explanation?.top_protective_factors || [],
      governance_flags: flags,
      checklist: reviewChecklist(application, flags),
      audit_note: "Static demo packet for portfolio review only. It is not a real lending record.",
    };
  }

  function governanceFlags(application) {
    const score = application.score_result;
    if (!score) return ["score_not_available"];
    const flags = [];
    if (!application.decision_result) flags.push("human_decision_not_recorded");
    if (score.risk_band === "high") flags.push("high_risk_application");
    if ((score.proxy_sensitivity_delta || 0) >= 0.2) flags.push("proxy_sensitive_score");
    if (score.decision_support?.recommendation_code === "manual_review_proxy_sensitive") {
      flags.push("manual_review_proxy_sensitive");
    }
    return flags;
  }

  function reviewChecklist(application, flags) {
    const score = application.score_result;
    const decision = application.decision_result;
    const rows = [
      {
        code: "verify_identity",
        title: "Verify borrower identity and application ownership",
        status: "suggested",
        evidence: application.borrower_email,
      },
      {
        code: "verify_affordability",
        title: "Review income stability and repayment affordability",
        status: score ? "required" : "suggested",
        evidence: application.purpose || null,
      },
    ];
    if (flags.includes("proxy_sensitive_score")) {
      rows.push({
        code: "review_proxy_context",
        title: "Review late-payment context before declining",
        status: "required",
        evidence: "proxy_sensitivity_delta >= 0.20",
      });
    }
    if (flags.includes("high_risk_application")) {
      rows.push({
        code: "senior_review",
        title: "Escalate high-risk cases before approval",
        status: "required",
        evidence: "risk_band=high",
      });
    }
    rows.push({
      code: "record_human_decision",
      title: "Record analyst decision and review note",
      status: decision ? "complete" : "required",
      evidence: decision?.note || null,
    });
    return rows;
  }

  function analyticsSegments(applications = demo.applications) {
    const scored = applications.filter((app) => app.score_result);
    const specs = [
      ["gender", (app) => app.behavioral_signals.gender || "unknown"],
      ["employment_status", (app) => app.behavioral_signals.employment_status || "unknown"],
      ["district", (app) => app.district || "unknown"],
    ];
    return specs.flatMap(([feature, getter]) => groupedRows(scored, getter).map((row) => ({
      segment_feature: feature,
      segment_value: row.key,
      n: row.items.length,
      avg_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      high_risk_share: share(row.items, (app) => app.score_result.risk_band === "high"),
    })));
  }

  function policyAnalytics(applications = demo.applications) {
    const scored = applications.filter((app) => app.score_result);
    const policies = [
      ["balanced_review", "Balanced inclusion and lender sustainability", 0.24, 0.58],
      ["inclusion_first", "More approvals with stronger manual monitoring", 0.34, 0.7],
      ["lender_protective", "Lower default tolerance", 0.18, 0.46],
      ["starter_loan_review", "Small first-loan policy", 0.28, 0.62],
    ].map(([policy, description, approve, decline]) => policyRow(scored, policy, description, approve, decline));

    const balanced = policies[0];
    const segments = groupedRows(scored, (app) => app.district || "unknown")
      .slice(0, 5)
      .map((row) => segmentPolicyRow(row.items, balanced.policy, "district", row.key, balanced.approve_threshold, balanced.decline_threshold));

    return {
      scored_application_count: scored.length,
      policies,
      segments,
      note: "Static demo policy lab uses synthetic probabilities and is not a lending rule.",
    };
  }

  function policyRow(apps, policy, description, approveThreshold, declineThreshold) {
    const actions = apps.map((app) => policyAction(app.score_result.high_risk_probability, approveThreshold, declineThreshold));
    const approveCount = actions.filter((action) => action === "approve").length;
    const reviewCount = actions.filter((action) => action === "review").length;
    const declineCount = actions.filter((action) => action === "decline").length;
    const approvedProbabilities = apps
      .filter((_, index) => actions[index] === "approve")
      .map((app) => app.score_result.high_risk_probability);
    const reviewProbabilities = apps
      .filter((_, index) => actions[index] === "review")
      .map((app) => app.score_result.high_risk_probability);
    const declinedProbabilities = apps
      .filter((_, index) => actions[index] === "decline")
      .map((app) => app.score_result.high_risk_probability);
    const highRiskApproved = apps.filter(
      (app, index) => actions[index] === "approve" && app.score_result.risk_band === "high",
    ).length;
    return {
      policy,
      description,
      approve_threshold: approveThreshold,
      decline_threshold: declineThreshold,
      n: apps.length,
      auto_approve_count: approveCount,
      manual_review_count: reviewCount,
      auto_decline_count: declineCount,
      auto_approval_rate: rate(approveCount, apps.length),
      manual_review_rate: rate(reviewCount, apps.length),
      auto_decline_rate: rate(declineCount, apps.length),
      mean_high_risk_probability: average(apps.map((app) => app.score_result.high_risk_probability)),
      mean_approved_probability: average(approvedProbabilities),
      mean_review_probability: average(reviewProbabilities),
      mean_declined_probability: average(declinedProbabilities),
      predicted_high_risk_auto_approved_count: highRiskApproved,
      predicted_high_risk_auto_approval_rate: rate(highRiskApproved, apps.length),
    };
  }

  function segmentPolicyRow(apps, policy, segmentFeature, segmentValue, approveThreshold, declineThreshold) {
    const actions = apps.map((app) => policyAction(app.score_result.high_risk_probability, approveThreshold, declineThreshold));
    return {
      policy,
      segment_feature: segmentFeature,
      segment_value: segmentValue,
      n: apps.length,
      auto_approval_rate: rate(actions.filter((action) => action === "approve").length, apps.length),
      manual_review_rate: rate(actions.filter((action) => action === "review").length, apps.length),
      auto_decline_rate: rate(actions.filter((action) => action === "decline").length, apps.length),
      mean_high_risk_probability: average(apps.map((app) => app.score_result.high_risk_probability)),
      predicted_high_risk_share: share(apps, (app) => app.score_result.risk_band === "high"),
    };
  }

  function policyAction(probability, approveThreshold, declineThreshold) {
    if (probability <= approveThreshold) return "approve";
    if (probability >= declineThreshold) return "decline";
    return "review";
  }

  function decisionAnalytics(applications = demo.applications) {
    const apps = applications.filter((app) => app.score_result);
    const decided = apps.filter((app) => app.decision_result);
    return {
      application_count: applications.length,
      decided_application_count: decided.length,
      decision_rows: decisionRows(decided, () => "all").map((row) => ({
        decision: row.decision,
        count: row.count,
        rate: rate(row.count, decided.length),
      })),
      policy_rows: decisionRows(decided, (app) => app.decision_result.policy_name || "unknown").map((row) => ({
        policy_name: row.key,
        decision: row.decision,
        count: row.count,
        rate: rate(row.count, row.groupSize),
      })),
      risk_rows: decisionRows(decided, (app) => app.score_result.risk_band).map((row) => ({
        risk_band: row.key,
        decision: row.decision,
        count: row.count,
        rate_within_risk_band: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      })),
      district_rows: decisionRows(decided, (app) => app.district || "unknown").map((row) => ({
        district: row.key,
        decision: row.decision,
        count: row.count,
        rate_within_district: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      })),
      recommendation_rows: decisionRows(decided, (app) => app.score_result.decision_support?.recommendation_code || "unknown").map((row) => ({
        recommendation_code: row.key,
        recommendation_title: row.items[0]?.score_result.decision_support?.title || row.key,
        decision: row.decision,
        count: row.count,
        rate_within_recommendation: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
      })),
      proxy_rows: decisionRows(decided, (app) => proxyBucket(app.score_result.proxy_sensitivity_delta)).map((row) => ({
        proxy_sensitivity_bucket: row.key,
        decision: row.decision,
        count: row.count,
        rate_within_bucket: rate(row.count, row.groupSize),
        mean_high_risk_probability: average(row.items.map((app) => app.score_result.high_risk_probability)),
        mean_proxy_sensitivity_delta: average(row.items.map((app) => app.score_result.proxy_sensitivity_delta)),
      })),
      note: "Static demo decision audit uses synthetic analyst decisions.",
    };
  }

  function decisionRows(apps, groupGetter) {
    return groupedRows(apps, groupGetter).flatMap((group) =>
      ["approve", "review", "decline"].map((decision) => {
        const items = group.items.filter((app) => app.decision_result?.decision === decision);
        return {
          key: group.key,
          decision,
          count: items.length,
          items,
          groupSize: group.items.length,
        };
      }).filter((row) => row.count > 0),
    );
  }

  function proxyBucket(value) {
    if ((value || 0) >= 0.2) return "high_proxy_sensitivity";
    if ((value || 0) >= 0.08) return "medium_proxy_sensitivity";
    return "low_proxy_sensitivity";
  }

  function groupedRows(items, getter) {
    const groups = {};
    items.forEach((item) => {
      const key = getter(item) || "unknown";
      groups[key] = groups[key] || [];
      groups[key].push(item);
    });
    return Object.entries(groups).map(([key, groupItems]) => ({ key, items: groupItems }));
  }

  function average(values) {
    const valid = values.filter((value) => value !== null && value !== undefined);
    if (!valid.length) return null;
    return valid.reduce((total, value) => total + Number(value), 0) / valid.length;
  }

  function share(items, predicate) {
    return items.length ? items.filter(predicate).length / items.length : 0;
  }

  function rate(count, total) {
    return total ? count / total : 0;
  }

  function portfolioCsv(applications = demo.applications) {
    const columns = [
      "application_id",
      "organization_id",
      "borrower_email",
      "status",
      "requested_amount",
      "district",
      "risk_band",
      "high_risk_probability",
      "proxy_sensitivity_delta",
      "decision",
      "policy_name",
    ];
    const rows = applications.map((app) => {
      const score = app.score_result || {};
      const decision = app.decision_result || {};
      return [
        app.id,
        app.organization_id,
        app.borrower_email,
        app.status,
        app.requested_amount,
        app.district || "",
        score.risk_band || "",
        score.high_risk_probability || "",
        score.proxy_sensitivity_delta || "",
        decision.decision || "",
        decision.policy_name || "",
      ];
    });
    return [columns, ...rows]
      .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
      .join("\n");
  }

  async function request(path, options = {}, session = {}) {
    const method = (options.method || "GET").toUpperCase();
    const body = parseBody(options);
    const cleanPath = path.split("?")[0];

    if (cleanPath === "/auth/login" && method === "POST") {
      const email = String(body.email || "").trim().toLowerCase();
      const user = demo.users[email];
      if (!user || user.password !== body.password) throw new Error("Invalid demo credentials");
      const token = `mock-token-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      demo.sessions[token] = email;
      return {
        access_token: token,
        token_type: "bearer",
        role: user.role,
        organization_id: user.organization_id || null,
      };
    }

    if (cleanPath === "/auth/register" && method === "POST") {
      const email = String(body.email || "").trim().toLowerCase();
      if (body.role && body.role !== "borrower") {
        throw new Error("Public registration is limited to borrower accounts");
      }
      const passwordViolations = passwordPolicyViolations(body.password);
      if (passwordViolations.length) {
        throw new Error(`Password does not meet the registration policy: ${passwordViolations.join(", ")}`);
      }
      if (demo.users[email]) throw new Error("User already exists in static demo");
      demo.users[email] = {
        email,
        role: "borrower",
        organization_id: null,
        password: body.password || "",
        created_at: nowIso(),
      };
      const token = `mock-token-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      demo.sessions[token] = email;
      return {
        access_token: token,
        token_type: "bearer",
        role: demo.users[email].role,
        organization_id: null,
      };
    }

    if (cleanPath === "/auth/logout" && method === "POST") {
      const user = currentUser(session);
      const revoked = Boolean(demo.sessions[session.token]);
      delete demo.sessions[session.token];
      addAudit("user_logged_out", "session", user.email, user.email, { role: user.role });
      return { revoked };
    }

    if (cleanPath === "/organizations" && method === "GET") {
      return clone(Object.values(demo.organizations));
    }

    if (cleanPath === "/applications" && method === "POST") {
      const user = currentUser(session);
      if (user.role !== "borrower") throw new Error("Borrower account required");
      validateApplicationPrivacy(body);
      if (!demo.organizations[body.organization_id]) throw new Error("Select a valid MFI organization");
      const app = createApplicationRecord(body, user.email);
      demo.applications.unshift(app);
      addAudit("application_created", "application", app.id, user.email, {
        mode: "static_demo",
        consent_confirmed: true,
        consent_version: body.consent_version,
      });
      return clone(app);
    }

    const appMatch = cleanPath.match(/^\/applications\/([^/]+)$/);
    if (appMatch && method === "GET") return clone(visibleApplication(decodeURIComponent(appMatch[1]), session));

    const timelineMatch = cleanPath.match(/^\/applications\/([^/]+)\/timeline$/);
    if (timelineMatch && method === "GET") {
      visibleApplication(decodeURIComponent(timelineMatch[1]), session);
      return clone(demo.timelines[decodeURIComponent(timelineMatch[1])] || []);
    }

    if (cleanPath === "/mfi/applications" && method === "GET") {
      const user = requireMfi(session);
      return clone(mfiApplications(user));
    }

    const scoreMatch = cleanPath.match(/^\/mfi\/applications\/([^/]+)\/score$/);
    if (scoreMatch && method === "POST") {
      const user = requireMfi(session);
      const app = mfiApplication(decodeURIComponent(scoreMatch[1]), user);
      app.score_result = buildScore(app);
      app.status = "scored";
      app.scored_at = nowIso();
      addTimeline(app.id, "application_scored", user.email, {
        model_version: app.score_result.model_version,
        risk_band: app.score_result.risk_band,
      });
      addAudit("application_scored", "application", app.id, user.email, { mode: "static_demo" });
      return clone(app);
    }

    const packetMatch = cleanPath.match(/^\/mfi\/applications\/([^/]+)\/review-packet$/);
    if (packetMatch && method === "GET") {
      const user = requireMfi(session);
      return clone(reviewPacket(mfiApplication(decodeURIComponent(packetMatch[1]), user)));
    }

    const decisionMatch = cleanPath.match(/^\/mfi\/applications\/([^/]+)\/decision$/);
    if (decisionMatch && method === "POST") {
      const user = requireMfi(session);
      const app = mfiApplication(decodeURIComponent(decisionMatch[1]), user);
      if (!app.score_result) throw new Error("Score the application before saving a decision");
      app.decision_result = createDecision(app.id, user.email, body);
      addTimeline(app.id, "application_decision_recorded", user.email, {
        decision: body.decision,
        policy_name: body.policy_name || "balanced_review",
      });
      addAudit("application_decision_recorded", "application", app.id, user.email, { decision: body.decision });
      return clone(app);
    }

    if (cleanPath === "/mfi/analytics/segments" && method === "GET") {
      const user = requireMfi(session);
      return clone(analyticsSegments(mfiApplications(user)));
    }

    if (cleanPath === "/mfi/analytics/policies" && method === "GET") {
      const user = requireMfi(session);
      return clone(policyAnalytics(mfiApplications(user)));
    }

    if (cleanPath === "/mfi/analytics/decisions" && method === "GET") {
      const user = requireMfi(session);
      return clone(decisionAnalytics(mfiApplications(user)));
    }

    if (cleanPath === "/admin/users" && method === "GET") {
      requireAdmin(session);
      return clone(
        Object.values(demo.users)
          .map(({ email, role, organization_id, created_at }) => ({
            email,
            role,
            organization_id: organization_id || null,
            created_at,
          }))
          .sort((left, right) => `${left.role}:${left.email}`.localeCompare(`${right.role}:${right.email}`)),
      );
    }

    if (cleanPath === "/admin/users" && method === "POST") {
      const user = requireAdmin(session);
      const email = String(body.email || "").trim().toLowerCase();
      if (body.role !== "mfi_analyst") throw new Error("Only MFI analyst accounts can be provisioned");
      if (!demo.organizations[body.organization_id]) throw new Error("Select a valid MFI organization");
      const passwordViolations = passwordPolicyViolations(body.password);
      if (passwordViolations.length) {
        throw new Error(`Password does not meet the registration policy: ${passwordViolations.join(", ")}`);
      }
      if (demo.users[email]) throw new Error("User already exists in static demo");
      demo.users[email] = {
        email,
        role: "mfi_analyst",
        organization_id: body.organization_id,
        password: body.password,
        created_at: nowIso(),
      };
      addAudit("staff_user_created", "user", email, user.email, {
        role: "mfi_analyst",
        organization_id: body.organization_id,
      });
      return clone({
        email,
        role: "mfi_analyst",
        organization_id: body.organization_id,
        created_at: demo.users[email].created_at,
      });
    }

    if (cleanPath === "/admin/organizations" && method === "POST") {
      const user = requireAdmin(session);
      const organizationId = String(body.id || "").trim().toLowerCase();
      if (demo.organizations[organizationId]) throw new Error("Organization already exists");
      demo.organizations[organizationId] = {
        id: organizationId,
        name: body.name,
        region: body.region,
        created_at: nowIso(),
      };
      addAudit("organization_created", "mfi_organization", organizationId, user.email, {
        name: body.name,
        region: body.region,
      });
      return clone(demo.organizations[organizationId]);
    }

    if (cleanPath === "/admin/audit-events" && method === "GET") {
      requireAdmin(session);
      return clone(demo.auditEvents);
    }

    if (cleanPath === "/admin/applications" && method === "DELETE") {
      const user = requireAdmin(session);
      const deletedCount = demo.applications.length;
      demo.applications = [];
      demo.timelines = {};
      addAudit("applications_cleared", "portfolio", "static-demo", user.email, { deleted_count: deletedCount });
      return { deleted_count: deletedCount };
    }

    throw new Error(`Static demo endpoint not implemented: ${method} ${cleanPath}`);
  }

  async function blob(path, session = {}) {
    if (path === "/mfi/applications/export.csv") {
      const user = requireMfi(session);
      return new Blob(
        [portfolioCsv(mfiApplications(user))],
        { type: "text/csv;charset=utf-8" },
      );
    }
    throw new Error(`Static demo file endpoint not implemented: ${path}`);
  }

  resetDemo();

  window.MicroScoreMockApi = {
    request,
    blob,
    resetDemo,
  };
})();
