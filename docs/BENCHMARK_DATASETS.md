# Public Benchmark Dataset Plan

The main current weakness of MicroScore is synthetic borrower-level data. The
Pavlodar layer is useful for local product design, but it is not evidence that
the scoring pipeline works on real borrowers.

MicroScore now has a public benchmark experiment scaffold alongside the
synthetic Pavlodar prototype. The first implemented benchmark target is UCI
Default of Credit Card Clients.

## Experiment Tracks

### Experiment A: Synthetic Pavlodar Prototype

Purpose:

- test the end-to-end research and product workflow
- simulate local district and settlement-type context
- expose leakage, proxy dependence, and fairness risks
- support demo portfolio analytics

Limitation:

- not real MFI borrower data
- regional borrower-level fields are modeled assumptions
- should not be used as evidence of real-world lending performance

### Experiment B: Public Credit-Risk Benchmark

Purpose:

- test the same modeling, calibration, error analysis, and explainability
  pipeline on real public credit-risk data
- separate product/local-context work from model-validity evidence
- make the project more credible for external reviewers

## Implemented First Benchmark

### UCI Default of Credit Card Clients

Official source:

- https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients

Why it is a good first benchmark:

- public academic benchmark
- 30,000 instances
- 23 features
- classification task
- no missing values listed by UCI
- has a DOI and citation metadata
- licensed under CC BY 4.0 on UCI

Why it fits MicroScore:

- credit-risk target
- includes payment history, bill amounts, and payment amounts
- lets the project test calibration, ROC-AUC, Brier score, error analysis, and
  explainability on real public data

Important caveat:

- it is credit-card default data from Taiwan, not Kazakhstan microfinance data
- it does not validate Pavlodar regional assumptions
- it should be presented as benchmark validation, not local deployment evidence

## How To Run The UCI Benchmark

Download the official `default of credit card clients.xls` file from UCI and
place it here:

```text
data/external/benchmarks/uci-default-credit-card-clients/raw/default of credit card clients.xls
```

Then run:

```powershell
.venv\Scripts\python -m microscore --benchmark uci-default
```

Or pass a custom local file path:

```powershell
.venv\Scripts\python -m microscore --benchmark uci-default --benchmark-data "C:\path\to\default of credit card clients.xls"
```

The benchmark writes artifacts to:

```text
reports/benchmark-artifacts/uci-default-credit-card-clients/
```

Current generated outputs:

- `SUMMARY.md`
- `manifest.json`
- `model_metrics.csv`
- `calibration_bins.csv`
- `top_features.csv`
- `error_analysis_summary.csv`
- `segment_error_analysis.csv`
- `false_positive_examples.csv`
- `false_negative_examples.csv`
- optional `calibration_curve.png`

## Current UCI Benchmark Results

Generated artifacts are stored under
`reports/benchmark-artifacts/uci-default-credit-card-clients/`.

| Model | Test ROC-AUC | Brier score | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Logistic Regression | 0.7104 | 0.2089 | 0.3679 | 0.6315 | 0.4649 |
| Random Forest | 0.7750 | 0.1587 | 0.5217 | 0.5607 | 0.5405 |

Initial interpretation:

- The public benchmark confirms that the pipeline can run on real public
  credit-risk data, not only on the synthetic Pavlodar prototype.
- Random Forest performs better than Logistic Regression on ranking and
  probability quality in this benchmark.
- Demographic/category variables appear in the explanation tables, so fairness
  and proxy-risk analysis still matter even on public benchmark data.
- This result does not validate Pavlodar regional assumptions or real MFI
  deployment.

## Optional Second Benchmark

### Home Credit Default Risk

Source:

- https://www.kaggle.com/c/home-credit-default-risk

Why it is useful later:

- larger lending dataset
- richer application and bureau-style tables
- closer to consumer credit workflows

Why it should be second:

- Kaggle access and competition terms add friction
- multi-table joins increase implementation complexity
- easier to make leakage mistakes without careful documentation

## Target Benchmark Outputs

The benchmark experiment should produce the same style of artifacts as the
current synthetic pipeline:

- model metrics
- ROC-AUC and Brier score
- calibration bins and calibration curve
- false-positive and false-negative analysis
- feature importance and local explanations
- model card updates
- comparison table: synthetic Pavlodar vs public benchmark

## Reporting Language

Use precise language:

- "The Pavlodar layer is synthetic and local-context oriented."
- "The public benchmark tests the modeling pipeline on real public credit-risk
  data."
- "Neither dataset proves readiness for real MFI lending in Kazakhstan."
- "Real deployment would require consent-based, anonymized pilot data and human
  oversight."

## Implementation Plan

1. Add a benchmark loader under `src/microscore/`. Done.
2. Keep benchmark raw data out of Git unless licensing clearly permits storage.
   Done through `.gitignore`.
3. Save benchmark artifacts under `reports/benchmark-artifacts/`. Done.
4. Add a short benchmark section to `docs/RESEARCH_PAPER.md`.
5. Add benchmark metrics to the README only after the experiment is reproducible.
