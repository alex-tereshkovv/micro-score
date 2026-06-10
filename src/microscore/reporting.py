"""Generate reproducible research artifacts for MicroScore."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .ablation import run_ablation_study
from .error_analysis import run_error_analysis
from .explainability import LocalExplanation, logistic_local_explanation
from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .modeling import (
    RANDOM_STATE,
    build_logistic_regression,
    build_models,
    calibration_table,
    evaluate_model,
    load_dataset,
    results_table,
)
from .paths import DEFAULT_DATA_PATH, PROJECT_ROOT
from .policy import run_policy_analysis

DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports" / "research-artifacts"


@dataclass(frozen=True)
class ResearchArtifactPaths:
    """Paths written by the research artifact generator."""

    output_dir: Path
    summary_markdown: Path
    manifest_json: Path
    model_metrics_csv: Path
    ablation_csv: Path
    calibration_csv: Path
    error_summary_csv: Path
    segment_error_csv: Path
    false_positive_examples_csv: Path
    false_negative_examples_csv: Path
    prediction_errors_csv: Path
    policy_analysis_csv: Path
    segment_policy_analysis_csv: Path
    explanation_summary_csv: Path
    explanation_factors_csv: Path
    plot_paths: tuple[Path, ...] = ()

    @property
    def files(self) -> tuple[Path, ...]:
        return (
            self.summary_markdown,
            self.manifest_json,
            self.model_metrics_csv,
            self.ablation_csv,
            self.calibration_csv,
            self.error_summary_csv,
            self.segment_error_csv,
            self.false_positive_examples_csv,
            self.false_negative_examples_csv,
            self.prediction_errors_csv,
            self.policy_analysis_csv,
            self.segment_policy_analysis_csv,
            self.explanation_summary_csv,
            self.explanation_factors_csv,
            *self.plot_paths,
        )


def _round_for_report(frame: pd.DataFrame, digits: int = 4) -> pd.DataFrame:
    result = frame.copy()
    numeric_columns = result.select_dtypes(include="number").columns
    result[numeric_columns] = result[numeric_columns].round(digits)
    return result


def _portable_path(path: str | Path) -> str:
    resolved = Path(path)
    try:
        return str(resolved.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _markdown_table(frame: pd.DataFrame, *, max_rows: int | None = None) -> str:
    display = frame.head(max_rows).copy() if max_rows else frame.copy()
    display = _round_for_report(display)
    if display.empty:
        return "_No rows._"

    columns = list(display.columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _column in columns) + " |"
    rows = [
        "| "
        + " | ".join(str(row[column]) for column in columns)
        + " |"
        for row in display.to_dict(orient="records")
    ]
    return "\n".join([header, separator, *rows])


def _model_results_and_calibration(
    frame: pd.DataFrame,
    *,
    model_factories: dict[str, Callable[[], Pipeline]],
    random_state: int,
    test_size: float,
    n_bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame, Pipeline, pd.DataFrame]:
    X, y = make_model_frame(frame, target=TARGET_COLUMN, drop_columns=DEFAULT_DROP_COLUMNS)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    results = []
    calibration_tables = []
    logistic_estimator: Pipeline | None = None

    for model_name, model_factory in model_factories.items():
        result = evaluate_model(
            model_name,
            model_factory(),
            X_train,
            X_test,
            y_train,
            y_test,
            random_state=random_state,
        )
        results.append(result)
        if model_name == "Logistic Regression":
            logistic_estimator = result.estimator

        y_probability = result.estimator.predict_proba(X_test)[:, 1]
        model_calibration = calibration_table(y_test, y_probability, n_bins=n_bins)
        model_calibration.insert(0, "model", model_name)
        calibration_tables.append(model_calibration)

    if logistic_estimator is None:
        logistic_estimator = build_logistic_regression(random_state=random_state)
        logistic_estimator.fit(X_train, y_train)

    return (
        results_table(results),
        pd.concat(calibration_tables, ignore_index=True),
        logistic_estimator,
        X_test,
    )


def _explanation_tables(explanation: LocalExplanation) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.DataFrame(
        [
            {
                "method": explanation.method,
                "baseline_log_odds": explanation.baseline_log_odds,
                "total_contribution": explanation.total_contribution,
                "predicted_log_odds": explanation.predicted_log_odds,
                "high_risk_probability": explanation.high_risk_probability,
            }
        ]
    )

    factor_rows = []
    for group_name, factors in (
        ("top_positive_factors", explanation.top_positive_factors),
        ("top_protective_factors", explanation.top_protective_factors),
        ("top_factors", explanation.top_factors),
    ):
        for rank, factor in enumerate(factors, start=1):
            factor_rows.append(
                {
                    "group": group_name,
                    "rank": rank,
                    "feature": factor.feature,
                    "value": factor.value,
                    "abs_value": factor.abs_value,
                    "direction": factor.direction,
                    "label": factor.label,
                }
            )

    return summary, pd.DataFrame(factor_rows)


def _write_calibration_plot(calibration: pd.DataFrame, output_path: Path) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    try:
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot([0, 1], [0, 1], color="#64747d", linestyle="--", label="Perfect calibration")

        for model_name, group in calibration.groupby("model"):
            clean = group.dropna(subset=["mean_predicted_probability", "actual_high_risk_rate"])
            ax.plot(
                clean["mean_predicted_probability"],
                clean["actual_high_risk_rate"],
                marker="o",
                label=model_name,
            )

        ax.set_title("MicroScore Calibration Curve")
        ax.set_xlabel("Mean predicted high-risk probability")
        ax.set_ylabel("Actual high-risk rate")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        return output_path
    except Exception:
        plt.close("all")
        return None


def _write_ablation_plot(ablation: pd.DataFrame, output_path: Path) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    try:
        plot_frame = ablation[ablation["model"] != "Dummy Classifier"].copy()
        plot_frame["label"] = plot_frame["scenario"] + " / " + plot_frame["model"]
        plot_frame = plot_frame.sort_values("test_roc_auc")

        fig_height = max(5, 0.32 * len(plot_frame))
        fig, ax = plt.subplots(figsize=(9, fig_height))
        colors = plot_frame["model"].map(
            {
                "Logistic Regression": "#078b84",
                "Random Forest": "#315f9f",
            }
        ).fillna("#64747d")
        ax.barh(plot_frame["label"], plot_frame["test_roc_auc"], color=colors)
        ax.axvline(0.5, color="#b53b3b", linestyle="--", linewidth=1, label="Random ranking")
        ax.set_title("MicroScore Feature-Group Ablation")
        ax.set_xlabel("Test ROC-AUC")
        ax.set_xlim(0, 1)
        ax.grid(True, axis="x", alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        return output_path
    except Exception:
        plt.close("all")
        return None


def _write_summary(
    output_path: Path,
    *,
    model_metrics: pd.DataFrame,
    ablation: pd.DataFrame,
    calibration: pd.DataFrame,
    error_summary: pd.DataFrame,
    segment_errors: pd.DataFrame,
    false_positive_examples: pd.DataFrame,
    false_negative_examples: pd.DataFrame,
    policy_analysis: pd.DataFrame,
    segment_policy_analysis: pd.DataFrame,
    explanation_summary: pd.DataFrame,
    explanation_factors: pd.DataFrame,
    artifact_paths: ResearchArtifactPaths,
) -> None:
    model_columns = [
        "model",
        "test_roc_auc",
        "test_brier_score",
        "test_precision",
        "test_recall",
        "test_f1",
    ]
    ablation_columns = [
        "scenario",
        "model",
        "feature_count",
        "test_roc_auc",
        "test_brier_score",
        "delta_test_roc_auc_vs_no_leakage",
    ]
    explanation_columns = [
        "group",
        "rank",
        "feature",
        "value",
        "direction",
    ]
    error_columns = [
        "error_type",
        "n",
        "share_of_test",
        "mean_high_risk_probability",
        "decision_meaning",
    ]
    segment_error_columns = [
        "segment_feature",
        "segment_value",
        "n",
        "false_positive_rate",
        "false_negative_rate",
    ]
    example_columns = [
        "row_index",
        "actual_credit_risk",
        "predicted_credit_risk",
        "high_risk_probability",
        "late_payment_count",
        "annual_income",
        "loan_application_amount",
        "decision_meaning",
    ]
    policy_columns = [
        "policy",
        "auto_approval_rate",
        "manual_review_rate",
        "auto_decline_rate",
        "high_risk_rate_among_approved",
        "high_risk_approval_rate",
        "good_borrower_auto_decline_rate",
        "expected_profit_per_applicant",
    ]
    segment_policy_columns = [
        "policy",
        "segment_feature",
        "segment_value",
        "n",
        "auto_approval_rate",
        "manual_review_rate",
        "auto_decline_rate",
    ]

    files = "\n".join(
        f"- `{path.name}`"
        for path in artifact_paths.files
        if path.name != output_path.name
    )

    text = f"""# MicroScore Research Artifacts

Generated by:

```powershell
.venv\\Scripts\\python -m microscore --reports
```

These artifacts are generated from the current synthetic borrower-level dataset.
They are useful for reproducible research review, but they are not evidence of
real-world lending validity.

## Files

{files}

## Model Metrics

{_markdown_table(model_metrics[model_columns])}

## Ablation Highlights

{_markdown_table(ablation[ablation_columns], max_rows=18)}

## Calibration Preview

{_markdown_table(calibration.head(12))}

## Error Analysis Summary

{_markdown_table(error_summary[error_summary["error_type"].notna()][error_columns])}

## Segment Error Preview

{_markdown_table(segment_errors[segment_error_columns], max_rows=12)}

## False Positive Examples

{_markdown_table(false_positive_examples[[column for column in example_columns if column in false_positive_examples.columns]], max_rows=8)}

## False Negative Examples

{_markdown_table(false_negative_examples[[column for column in example_columns if column in false_negative_examples.columns]], max_rows=8)}

## Threshold Policy Analysis

{_markdown_table(policy_analysis[policy_columns])}

## Segment Policy Preview

{_markdown_table(segment_policy_analysis[segment_policy_columns], max_rows=16)}

## Example Local Explanation

{_markdown_table(explanation_summary)}

## Top Explanation Factors

{_markdown_table(explanation_factors[explanation_columns], max_rows=16)}
"""
    output_path.write_text(text, encoding="utf-8")


def generate_research_artifacts(
    data_path: str | Path = DEFAULT_DATA_PATH,
    *,
    frame: pd.DataFrame | None = None,
    output_dir: str | Path = DEFAULT_REPORTS_DIR,
    model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    ablation_model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
    n_bins: int = 10,
) -> ResearchArtifactPaths:
    """Generate CSV, Markdown, and optional PNG research artifacts."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_frame = frame.copy() if frame is not None else load_dataset(data_path)
    factories = model_factories or build_models(random_state)
    ablation_factories = ablation_model_factories or None

    model_metrics, calibration, logistic_estimator, X_test = _model_results_and_calibration(
        base_frame,
        model_factories=factories,
        random_state=random_state,
        test_size=test_size,
        n_bins=n_bins,
    )
    ablation = run_ablation_study(
        frame=base_frame,
        model_factories=ablation_factories,
        random_state=random_state,
        test_size=test_size,
    )
    explanation = logistic_local_explanation(logistic_estimator, X_test.iloc[[0]])
    explanation_summary, explanation_factors = _explanation_tables(explanation)
    error_analysis = run_error_analysis(
        frame=base_frame,
        random_state=random_state,
        test_size=test_size,
    )
    policy_analysis = run_policy_analysis(
        frame=base_frame,
        random_state=random_state,
        test_size=test_size,
    )

    paths = ResearchArtifactPaths(
        output_dir=output_path,
        summary_markdown=output_path / "SUMMARY.md",
        manifest_json=output_path / "manifest.json",
        model_metrics_csv=output_path / "model_metrics.csv",
        ablation_csv=output_path / "ablation_study.csv",
        calibration_csv=output_path / "calibration_bins.csv",
        error_summary_csv=output_path / "error_analysis_summary.csv",
        segment_error_csv=output_path / "segment_error_analysis.csv",
        false_positive_examples_csv=output_path / "false_positive_examples.csv",
        false_negative_examples_csv=output_path / "false_negative_examples.csv",
        prediction_errors_csv=output_path / "prediction_errors.csv",
        policy_analysis_csv=output_path / "policy_analysis.csv",
        segment_policy_analysis_csv=output_path / "segment_policy_analysis.csv",
        explanation_summary_csv=output_path / "example_explanation_summary.csv",
        explanation_factors_csv=output_path / "example_explanation_factors.csv",
        plot_paths=(),
    )

    _round_for_report(model_metrics).to_csv(paths.model_metrics_csv, index=False)
    _round_for_report(ablation).to_csv(paths.ablation_csv, index=False)
    _round_for_report(calibration).to_csv(paths.calibration_csv, index=False)
    _round_for_report(error_analysis.summary).to_csv(paths.error_summary_csv, index=False)
    _round_for_report(error_analysis.segment_errors).to_csv(
        paths.segment_error_csv,
        index=False,
    )
    _round_for_report(error_analysis.false_positive_examples).to_csv(
        paths.false_positive_examples_csv,
        index=False,
    )
    _round_for_report(error_analysis.false_negative_examples).to_csv(
        paths.false_negative_examples_csv,
        index=False,
    )
    _round_for_report(error_analysis.all_predictions).to_csv(
        paths.prediction_errors_csv,
        index=False,
    )
    _round_for_report(policy_analysis.policy_table).to_csv(
        paths.policy_analysis_csv,
        index=False,
    )
    _round_for_report(policy_analysis.segment_policy_table).to_csv(
        paths.segment_policy_analysis_csv,
        index=False,
    )
    _round_for_report(explanation_summary).to_csv(
        paths.explanation_summary_csv,
        index=False,
    )
    _round_for_report(explanation_factors).to_csv(paths.explanation_factors_csv, index=False)

    plot_paths = tuple(
        path
        for path in (
            _write_calibration_plot(calibration, output_path / "calibration_curve.png"),
            _write_ablation_plot(ablation, output_path / "ablation_roc_auc.png"),
        )
        if path is not None
    )
    paths = ResearchArtifactPaths(
        output_dir=paths.output_dir,
        summary_markdown=paths.summary_markdown,
        manifest_json=paths.manifest_json,
        model_metrics_csv=paths.model_metrics_csv,
        ablation_csv=paths.ablation_csv,
        calibration_csv=paths.calibration_csv,
        error_summary_csv=paths.error_summary_csv,
        segment_error_csv=paths.segment_error_csv,
        false_positive_examples_csv=paths.false_positive_examples_csv,
        false_negative_examples_csv=paths.false_negative_examples_csv,
        prediction_errors_csv=paths.prediction_errors_csv,
        policy_analysis_csv=paths.policy_analysis_csv,
        segment_policy_analysis_csv=paths.segment_policy_analysis_csv,
        explanation_summary_csv=paths.explanation_summary_csv,
        explanation_factors_csv=paths.explanation_factors_csv,
        plot_paths=plot_paths,
    )

    manifest = {
        "project": "MicroScore",
        "data_path": _portable_path(data_path),
        "rows": int(len(base_frame)),
        "target": TARGET_COLUMN,
        "random_state": random_state,
        "test_size": test_size,
        "n_bins": n_bins,
        "files": [path.name for path in paths.files],
        "data_warning": "Synthetic borrower-level data; not validated for real lending.",
    }
    paths.manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_summary(
        paths.summary_markdown,
        model_metrics=model_metrics,
        ablation=ablation,
        calibration=calibration,
        error_summary=error_analysis.summary,
        segment_errors=error_analysis.segment_errors,
        false_positive_examples=error_analysis.false_positive_examples,
        false_negative_examples=error_analysis.false_negative_examples,
        policy_analysis=policy_analysis.policy_table,
        segment_policy_analysis=policy_analysis.segment_policy_table,
        explanation_summary=explanation_summary,
        explanation_factors=explanation_factors,
        artifact_paths=paths,
    )
    return paths
