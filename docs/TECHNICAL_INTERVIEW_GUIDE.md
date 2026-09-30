# MicroScore Technical Interview Guide

This guide is for explaining MicroScore in your own words. Do not memorize it
as a script. Use it to check that you can move from a simple explanation to the
technical detail and then show the corresponding code or evidence.

## The 60-Second Explanation

MicroScore asks whether alternative behavioral data could help a regional MFI
review borrowers who have little formal credit history. I built both a research
pipeline and a working decision-support prototype. The research compares
Logistic Regression and Random Forest, checks calibration, errors, feature
ablation, segment behavior, and threshold policies. The product connects those
ideas to borrower, analyst, and admin workflows through a FastAPI backend,
SQLite persistence, a static frontend, audit events, and a model registry.

The most important result is a limitation: the synthetic model looks moderately
strong, but most of that performance depends on `late_payment_count`. Removing
that feature drops ROC-AUC close to `0.5`. So I do not claim the model is ready
for lending. The project demonstrates how to expose that weakness, keep a human
in the loop, and define what evidence would be required before a real pilot.

## 1. Why Logistic Regression?

### Short answer

It is a strong, interpretable baseline for binary risk probability. Its linear
coefficients make the direction of each transformed feature inspectable, and it
supports additive local contribution explanations in the analyst workflow.

### Deeper answer

- The target is binary: higher-risk or lower-risk outcome.
- The pipeline imputes missing values, standardizes numeric inputs, and one-hot
  encodes categorical inputs before fitting the classifier.
- `class_weight="balanced"` reduces the tendency to ignore the minority class.
- The model returns probabilities, which are needed for calibration analysis,
  threshold policies, and Monte Carlo portfolio simulation.
- Random Forest is kept as a nonlinear comparison. A higher ROC-AUC from a more
  complex model does not automatically make it the right operational model,
  especially when local explanations and evidence quality matter.

### Important caveat

Logistic Regression is interpretable only relative to its transformed inputs
and assumptions. A coefficient is not proof of causality, fairness, or safe use.
Correlated features, proxy variables, and poor data can still make an apparently
simple model misleading.

### Show the evidence

- Model pipelines: `src/microscore/modeling.py`
- API scoring and local explanations: `src/microscore_api/scoring.py`
- Model limitations and intended use: `docs/MODEL_CARD.md`

## 2. What Does ROC-AUC Mean?

### Short answer

ROC-AUC measures ranking quality. It is the probability that the model assigns
a higher risk score to a randomly chosen positive case than to a randomly chosen
negative case. `0.5` is random ranking; `1.0` is perfect ranking.

### What it does not tell you

- It does not choose an approval threshold.
- It does not say whether a predicted `30%` risk occurs about `30%` of the time.
- It does not directly measure profit, inclusion, false-negative cost, or
  fairness between groups.
- It can look acceptable even when the underlying data contains a dominant
  proxy or does not match the deployment population.

That is why MicroScore reports Brier score and calibration, confusion-matrix
errors, ablation, segment metrics, and policy outcomes alongside ROC-AUC.

### Show the evidence

- Metric calculation: `src/microscore/modeling.py`
- Calibration and errors: `src/microscore/error_analysis.py`
- Generated results: `reports/research-artifacts/`

## 3. Why Is `late_payment_count` A Problem?

### Short answer

It is not automatically a bad feature. The problem is that it nearly reproduces
the entire synthetic model's performance by itself. That makes the result
fragile and weakens the claim that the model helps genuinely thin-file borrowers
who may have little or no repayment history.

### Evidence chain

1. The full synthetic Logistic Regression reaches ROC-AUC about `0.806` and the
   Random Forest about `0.830`.
2. `late_payment_count` alone reaches about `0.827`.
3. Without it, performance falls to about `0.486-0.492`, near random ranking.
4. Confident false negatives often have `late_payment_count = 0`.

This suggests that the synthetic generator encoded too much target information
into one repayment-history field and too little independent behavioral signal
into the remaining features.

### Risks to name precisely

- Proxy risk: the feature may stand in for access to prior formal credit, which
  can disadvantage the very thin-file group the project intends to help.
- Construct mismatch: prior late payment is repayment history, not a new
  alternative-data signal.
- Data-generation dependence: synthetic correlations may be stronger and
  cleaner than they would be in reality.
- Generalization risk: the relationship may not persist across time, lenders,
  districts, or borrower populations.

The correct response is not to silently delete the feature. It is to report the
dependence, test both versions, monitor the feature, and require real validation.

### Show the evidence

- Proxy audit: `src/microscore/audit.py`
- Ablation scenarios: `src/microscore/ablation.py`
- Monitoring boundary: `docs/PROXY_FEATURE_MONITORING.md`

## 4. What Does Ablation Show?

### Short answer

Ablation removes one feature or feature group and retrains the model. The change
in held-out performance tells us how much the result depends on that information.

### MicroScore interpretation

The raw feature set can produce an unrealistically high diagnostic ceiling when
leakage-like variables are present. The no-leakage baseline is lower but still
moderate. Removing `late_payment_count`, or using only behavioral features,
drops performance close to random. Regional variables alone also do not solve
the problem.

This does not prove that the remaining variables have zero value in every real
dataset. It shows that this synthetic dataset does not yet contain sufficient
independent signal for the intended thin-file claim.

### Show the evidence

- Study implementation: `src/microscore/ablation.py`
- Report generation: `src/microscore/reporting.py`
- Result table: `reports/research-artifacts/ablation_study.csv`

## 5. How Do You Know The Ablation Is Not One Lucky Split?

### Short answer

I do not rely on one point estimate. I repeat the baseline and thin-file
experiments across ten stratified splits, bootstrap the fixed held-out sample
1,000 times, and test deterministic input shifts. The baseline stays around
`0.83` mean ROC-AUC, while the no-`late_payment_count` Random Forest stays near
chance at `0.501` mean ROC-AUC. Its held-out bootstrap interval spans `0.5`.

The missing-history stress is operationally important: it changes about half
of Random Forest classifications at the diagnostic threshold. That supports a
data-availability warning, but it still does not replace temporal or external
validation.

### Show the evidence

- Protocol: `docs/ROBUSTNESS_AND_UNCERTAINTY.md`
- Implementation: `src/microscore/robustness.py`
- Summary: `reports/research-artifacts/robustness_summary.csv`
- Tests: `tests/test_robustness.py`

## 6. Why Threshold Policies Instead Of One Cutoff?

### Short answer

A probability is not a decision. The policy layer converts predicted risk into
three zones: approve below a lower threshold, decline above an upper threshold,
and send the uncertain middle band to human review.

### Trade-off

A stricter policy protects the lender but reduces access and increases declines.
An inclusion-first policy approves more applicants but accepts more high-risk
cases. A wide review band can reduce automatic decisions, but it creates analyst
workload. No threshold is objectively correct without explicit costs, capacity,
fairness goals, and validated probabilities.

MicroScore therefore compares named scenarios rather than hiding the choice in
one default number. It reports approval, review, decline, bad-borrower approval,
good-borrower decline, segment outcomes, and illustrative financial results.

### Show the evidence

- Policy definitions and validation: `src/microscore/policy.py`
- Single-threshold analysis: `src/microscore/decision.py`
- Product integration: `src/microscore_api/analytics.py`

## 7. What Does Monte Carlo Add?

### Short answer

The deterministic policy table gives one result for one set of probabilities.
Monte Carlo shows a range of portfolio outcomes when macro conditions and model
calibration are uncertain.

### Important design choices

- It does not randomly change or re-score an individual borrower.
- A shared macro shock creates correlated movement across the portfolio.
- Application-level shocks represent residual calibration uncertainty.
- The baseline, adverse, and severe scenarios use common random numbers, so
  their differences are less dominated by unrelated simulation noise.
- A seed, assumptions, model version, portfolio fingerprint, and result are
  stored so a run can be reproduced and audited.

The outputs are methodological scenario ranges, not forecasts, regulatory VaR,
or calibrated KZT profit. The current probabilities and financial assumptions
are not based on real local MFI outcomes.

### Show the evidence

- Method: `docs/MONTE_CARLO_METHODOLOGY.md`
- Engine: `src/microscore_api/simulation.py`
- Run registry and tenant scope: `src/microscore_api/database.py`

## 8. How Do Frontend, API, And Database Fit Together?

### Short answer

The static frontend supports two runtime modes. On GitHub Pages it talks to an
in-browser synthetic API. In local mode it calls FastAPI. FastAPI owns the typed
contracts, authentication, authorization, application lifecycle, scoring,
decisions, audit events, model registry, and simulations. The current runtime
repository persists those records in SQLite.

### Request path example

1. A borrower submits an application in `apps/web/`.
2. Pydantic schemas in `src/microscore_api/schemas.py` validate the payload.
3. FastAPI routes in `src/microscore_api/main.py` enforce role and tenant scope.
4. The repository in `src/microscore_api/database.py` stores the application.
5. The scoring service uses the active model version and returns probability,
   risk band, explanation, warnings, and provenance.
6. The analyst records a human decision; lifecycle rules prevent silent changes
   to terminal applications, and the action is audited.

### Why two frontend modes?

The browser-only mode makes the whole workflow publicly inspectable without
hosting real user data or requiring a reviewer to install Python. It proves the
interaction design, not backend deployment. Local mode exercises the actual API
and persistence layer.

### Database boundary

SQLite is appropriate as the default local backend because it is simple and
fully reproducible. PostgreSQL Runtime v1 now executes the same 52-method
repository contract and is tested against disposable PostgreSQL 16. That closes
the code/runtime parity gap, but it does not prove managed backups, restore
drills, retention, monitoring, high availability, or secret rotation.

### Show the evidence

- Architecture and data flow: `docs/ARCHITECTURE.md`
- Frontend runtime selection: `apps/web/app.js`
- API: `src/microscore_api/main.py`
- SQLite repository: `src/microscore_api/database.py`
- PostgreSQL boundary: `src/microscore_api/postgres_repository.py`
- PostgreSQL runtime: `src/microscore_api/postgres_runtime.py`
- Disposable runtime proof: `scripts/postgresql-runtime-smoke.py`

## 9. Why Human-In-The-Loop?

The data is synthetic, the model is not locally validated, probabilities may be
miscalibrated, and threshold choices contain social and financial judgments.
The system therefore presents a recommendation and evidence to an analyst. It
does not claim that a score makes a legal or ethical lending decision.

Human review alone is not a complete safeguard: reviewers can introduce bias or
rubber-stamp the model. That is why MicroScore also records decision history,
model provenance, lifecycle events, and segment outcomes.

## 10. What Are The Strongest Engineering Decisions?

- The same research package powers experimentation and API scoring instead of
  duplicating model logic.
- Typed request/response schemas reject unknown or unsafe application fields.
- Organization scoping is enforced in repository and API workflows.
- Model versions and score provenance are immutable after the decision context
  is created; later activation marks old scores stale rather than rewriting them.
- The public demo is deliberately separated from real-data capability.
- Tests cover research logic, API privacy and lifecycle, repository behavior,
  browser workflows, migration artifacts, and live smoke paths.

## 11. What Would You Change With Real Pilot Data?

1. Define the target and observation window with the MFI before training.
2. Use consented, minimized data and separate identifiers from modeling fields.
3. Split data temporally and, if possible, by institution or geography.
4. Re-run leakage, proxy, ablation, calibration, and segment analysis.
5. Calibrate probabilities and policy economics on observed outcomes.
6. Compare Logistic Regression with nonlinear models, but select on evidence,
   stability, interpretability, and operational cost rather than ROC-AUC alone.
7. Establish monitoring, appeal, override, incident, and retraining procedures.
8. Complete production identity, secrets, managed PostgreSQL operations,
   backup/restore, deployment, and independent security/privacy review before
   handling real borrower records.

## Rapid-Fire Questions

**Why not deep learning?**  The dataset and evidence do not justify it. A more
complex model would increase explanation and validation cost without solving the
dominant data-quality problem.

**Is `0.830` a good ROC-AUC?**  It is moderate-to-strong ranking on this held-out
synthetic split, but it is not deployment evidence. The ablation shows why the
headline number must not be read alone.

**Why keep Random Forest?**  It tests whether nonlinear interactions add useful
ranking power and provides a benchmark against the interpretable baseline.

**Why is Brier score useful?**  It measures squared error of the probabilities,
so it is sensitive to calibration as well as correctness. Lower is better.

**Why can accuracy mislead?**  A majority-class prediction can look accurate on
imbalanced data while failing the cases that matter.

**Why is the UCI result not enough?**  It uses real data and validates the
pipeline, but it represents Taiwan credit-card customers, not thin-file
borrowers at a Kazakhstan MFI.

**What is the biggest current risk?**  Claiming more external validity than the
data supports. The project controls that risk through explicit evidence classes,
non-use statements, and blocked pre-pilot readiness.

**What is your most important negative result?**  Removing
`late_payment_count` collapses ranking performance. That result changed the
project from a simple accuracy demo into a study of evidence quality and policy.

## Ownership Check

Before presenting the project, make sure you can:

- reproduce the main metrics and explain which dataset each one uses;
- draw the request path from browser to API to repository without notes;
- explain a probability, a risk band, and a policy action as different things;
- identify where tenant scope and lifecycle rules are enforced;
- run one ablation and one full quality check;
- name three claims the project intentionally does not make;
- describe which design decisions you made, which tools assisted you, and how
  you verified the resulting code and evidence.

If you cannot explain a central path yet, narrow the claim and practice by
opening the relevant implementation. Credibility comes from understanding the
trade-offs and limits, not from reciting every feature.
