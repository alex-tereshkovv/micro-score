# MicroScore Reports

This folder is for reproducible research artifacts generated from the current
MicroScore pipeline.

Generate the artifacts with:

```powershell
.venv\Scripts\python -m microscore --reports
```

Default output:

```text
reports/research-artifacts/
```

Expected files:

- `SUMMARY.md`
- `manifest.json`
- `model_metrics.csv`
- `ablation_study.csv`
- `calibration_bins.csv`
- `error_analysis_summary.csv`
- `segment_error_analysis.csv`
- `false_positive_examples.csv`
- `false_negative_examples.csv`
- `prediction_errors.csv`
- `policy_analysis.csv`
- `segment_policy_analysis.csv`
- `example_explanation_summary.csv`
- `example_explanation_factors.csv`
- `calibration_curve.png`, when plotting dependencies are available
- `ablation_roc_auc.png`, when plotting dependencies are available

These files are generated from synthetic borrower-level data. They are useful
for research review and portfolio presentation, but they should not be treated
as validation for real lending decisions.
