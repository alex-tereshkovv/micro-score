# Model Robustness And Uncertainty

## Purpose

MicroScore has two separate uncertainty layers:

1. **Model robustness** asks whether the score survives resampling, feature
   loss, and controlled input shifts.
2. **Portfolio Monte Carlo** asks how a fixed set of stored scores may translate
   into approvals, defaults, exposure, and a one-period result under policy and
   macro assumptions.

The second layer cannot repair a fragile first layer. This document defines the
model-robustness protocol implemented in `src/microscore/robustness.py`.

## Protocol

### Repeated stratified splits

The leakage-safe baseline and the thin-file ablation that removes
`late_payment_count` are retrained on ten deterministic 80/20 splits:

```text
7, 19, 42, 73, 101, 137, 211, 307, 401, 509
```

Each run stores model, scenario, seed, held-out class rate, ROC-AUC, Brier score,
accuracy, precision, recall, and F1. The summary reports mean, standard
deviation, percentiles, and observed range. The observed range is a split
stability diagnostic, not a temporal test or a population confidence interval.

### Held-out bootstrap intervals

For the fixed `random_state=42` split, the suite performs 1,000 stratified
bootstrap replicates. Negative and positive examples are sampled separately so
ROC-AUC is defined in every replicate. The output stores 95% percentile
intervals for ROC-AUC and Brier score.

These intervals describe sampling uncertainty conditional on the current
synthetic dataset and split. They do not establish temporal, geographic,
institutional, or causal validity.

### Controlled covariate-shift stress

Models trained on the original training data score the same held-out records
under four deterministic scenarios:

| Scenario | Perturbation | Question |
| --- | --- | --- |
| `baseline` | No change | Reference result |
| `digital_access_contraction` | Mobile logins and transfers ×0.40; ATM use ×1.20 | Is ranking sensitive to a lower-digital-access context? |
| `affordability_pressure` | Income, balance, deposits ×0.75; debt and requested amount ×1.15 | How much do financial-pressure inputs move the score? |
| `repayment_history_missing` | `late_payment_count` set missing and imputed by the fitted pipeline | What happens if the dominant proxy is unavailable at scoring time? |

The suite records metric deltas, mean and 95th-percentile absolute probability
movement, and the share of classifications that cross the diagnostic 0.50
threshold. These perturbations are sensitivity probes, not forecasts or
validated economic shocks.

## Current Synthetic Result

Across ten split seeds, the leakage-safe models remain relatively stable while
the thin-file ablation remains near random:

| Scenario | Model | Mean ROC-AUC | Observed range |
| --- | --- | ---: | ---: |
| Leakage-safe baseline | Logistic Regression | 0.826 | 0.806-0.844 |
| Leakage-safe baseline | Random Forest | 0.829 | 0.818-0.844 |
| No `late_payment_count` | Logistic Regression | 0.469 | 0.444-0.492 |
| No `late_payment_count` | Random Forest | 0.501 | 0.474-0.540 |

The fixed-split 95% bootstrap ROC-AUC intervals are `[0.781, 0.829]` and
`[0.804, 0.853]` for the two baselines, versus `[0.445, 0.529]` and
`[0.448, 0.532]` after removing `late_payment_count`.

When repayment history is unavailable at scoring time, ROC-AUC falls by about
0.32. Mean absolute probability movement is about 0.284-0.287, and 39.2% of
Logistic Regression classifications and 50.2% of Random Forest classifications
cross the 0.50 threshold. The correct interpretation is dependency risk, not a
claim that missing values will behave this way in a real MFI population.

## Reproducibility

Run the suite directly:

```powershell
.venv\Scripts\python -m microscore --robustness
```

Regenerate all research artifacts:

```powershell
.venv\Scripts\python -m microscore --reports
```

Primary outputs:

- `reports/research-artifacts/robustness_split_runs.csv`
- `reports/research-artifacts/robustness_summary.csv`
- `reports/research-artifacts/bootstrap_intervals.csv`
- `reports/research-artifacts/covariate_shift_stress.csv`
- `reports/research-artifacts/robustness_roc_auc.png`

The manifest records seeds, iteration count, confidence level, and shift names.
Automated proof is in `tests/test_robustness.py` and `tests/test_reporting.py`.

## Decision Boundary

Passing this suite means the code is deterministic and the synthetic finding is
not explained by one favorable split. It does **not** mean the model is stable
over time, transferable to Kazakhstan borrowers, calibrated for an MFI, fair,
or safe for automated lending. Those claims remain blocked pending consented
local outcomes, temporal validation, external review, and production monitoring.
