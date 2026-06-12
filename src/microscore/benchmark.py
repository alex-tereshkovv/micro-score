"""Public benchmark experiments for MicroScore."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .error_analysis import run_error_analysis
from .features import TARGET_COLUMN, make_model_frame
from .modeling import (
    RANDOM_STATE,
    build_models,
    calibration_table,
    evaluate_model,
    results_table,
)
from .paths import PROJECT_ROOT

UCI_DEFAULT_DATASET_PAGE = (
    "https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients"
)
UCI_DEFAULT_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "external"
    / "benchmarks"
    / "uci-default-credit-card-clients"
)
DEFAULT_UCI_DEFAULT_DATA_PATH = UCI_DEFAULT_DATA_DIR / "raw" / "default of credit card clients.xls"
DEFAULT_BENCHMARK_REPORTS_DIR = (
    PROJECT_ROOT / "reports" / "benchmark-artifacts" / "uci-default-credit-card-clients"
)

UCI_ID_COLUMNS = ("customer_id",)
UCI_SEGMENT_COLUMNS = ("sex", "education", "marriage")
UCI_EXAMPLE_COLUMNS = (
    "customer_id",
    "limit_balance",
    "sex",
    "education",
    "marriage",
    "age",
    "payment_status_sep",
    "payment_status_aug",
    "payment_status_jul",
    "bill_amount_sep",
    "payment_amount_sep",
)

_RAW_COLUMN_MAP = {
    "ID": "customer_id",
    "id": "customer_id",
    "X1": "limit_balance",
    "LIMIT_BAL": "limit_balance",
    "X2": "sex",
    "SEX": "sex",
    "X3": "education",
    "EDUCATION": "education",
    "X4": "marriage",
    "MARRIAGE": "marriage",
    "X5": "age",
    "AGE": "age",
    "X6": "payment_status_sep",
    "PAY_0": "payment_status_sep",
    "X7": "payment_status_aug",
    "PAY_2": "payment_status_aug",
    "X8": "payment_status_jul",
    "PAY_3": "payment_status_jul",
    "X9": "payment_status_jun",
    "PAY_4": "payment_status_jun",
    "X10": "payment_status_may",
    "PAY_5": "payment_status_may",
    "X11": "payment_status_apr",
    "PAY_6": "payment_status_apr",
    "X12": "bill_amount_sep",
    "BILL_AMT1": "bill_amount_sep",
    "X13": "bill_amount_aug",
    "BILL_AMT2": "bill_amount_aug",
    "X14": "bill_amount_jul",
    "BILL_AMT3": "bill_amount_jul",
    "X15": "bill_amount_jun",
    "BILL_AMT4": "bill_amount_jun",
    "X16": "bill_amount_may",
    "BILL_AMT5": "bill_amount_may",
    "X17": "bill_amount_apr",
    "BILL_AMT6": "bill_amount_apr",
    "X18": "payment_amount_sep",
    "PAY_AMT1": "payment_amount_sep",
    "X19": "payment_amount_aug",
    "PAY_AMT2": "payment_amount_aug",
    "X20": "payment_amount_jul",
    "PAY_AMT3": "payment_amount_jul",
    "X21": "payment_amount_jun",
    "PAY_AMT4": "payment_amount_jun",
    "X22": "payment_amount_may",
    "PAY_AMT5": "payment_amount_may",
    "X23": "payment_amount_apr",
    "PAY_AMT6": "payment_amount_apr",
    "Y": TARGET_COLUMN,
    "default payment next month": TARGET_COLUMN,
    "default_payment_next_month": TARGET_COLUMN,
    "default.payment.next.month": TARGET_COLUMN,
}


@dataclass(frozen=True)
class BenchmarkArtifactPaths:
    """Paths written by the public benchmark artifact generator."""

    output_dir: Path
    summary_markdown: Path
    manifest_json: Path
    model_metrics_csv: Path
    calibration_csv: Path
    top_features_csv: Path
    error_summary_csv: Path
    segment_error_csv: Path
    false_positive_examples_csv: Path
    false_negative_examples_csv: Path
    plot_paths: tuple[Path, ...] = ()

    @property
    def files(self) -> tuple[Path, ...]:
        return (
            self.summary_markdown,
            self.manifest_json,
            self.model_metrics_csv,
            self.calibration_csv,
            self.top_features_csv,
            self.error_summary_csv,
            self.segment_error_csv,
            self.false_positive_examples_csv,
            self.false_negative_examples_csv,
            *self.plot_paths,
        )


def _column_key(column: object) -> str:
    return " ".join(str(column).strip().split())


def _map_unknown_category(value: object, mapping: dict[int, str]) -> str:
    if pd.isna(value):
        return "unknown"
    try:
        key = int(value)
    except (TypeError, ValueError):
        return str(value).strip().lower().replace(" ", "_") or "unknown"
    return mapping.get(key, f"unknown_code_{key}")


def _label_uci_categories(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "sex" in result.columns:
        result["sex"] = result["sex"].map(
            lambda value: _map_unknown_category(value, {1: "male", 2: "female"})
        )
    if "education" in result.columns:
        result["education"] = result["education"].map(
            lambda value: _map_unknown_category(
                value,
                {
                    0: "unknown",
                    1: "graduate_school",
                    2: "university",
                    3: "high_school",
                    4: "other",
                    5: "other",
                    6: "other",
                },
            )
        )
    if "marriage" in result.columns:
        result["marriage"] = result["marriage"].map(
            lambda value: _map_unknown_category(
                value,
                {
                    0: "unknown",
                    1: "married",
                    2: "single",
                    3: "other",
                },
            )
        )
    return result


def normalize_uci_default_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize the UCI credit-card default dataset to MicroScore conventions."""

    renamed_columns = {
        column: _RAW_COLUMN_MAP.get(_column_key(column), _column_key(column).lower())
        for column in frame.columns
        if not str(column).lower().startswith("unnamed")
    }
    result = frame.loc[:, list(renamed_columns)].rename(columns=renamed_columns).copy()

    if TARGET_COLUMN not in result.columns:
        raise ValueError(
            "Could not find the UCI target column. Expected one of: "
            "'Y', 'default payment next month', or 'default_payment_next_month'."
        )

    for column in result.columns:
        if column == "customer_id":
            continue
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result.dropna(subset=[TARGET_COLUMN]).copy()
    result[TARGET_COLUMN] = result[TARGET_COLUMN].astype(int)
    result = _label_uci_categories(result)
    result = result.reset_index(drop=True)

    feature_count = len([column for column in result.columns if column != TARGET_COLUMN])
    if feature_count < 5:
        raise ValueError("UCI benchmark frame has too few usable feature columns.")

    return result


def _read_csv_candidates(path: Path) -> tuple[pd.DataFrame, ...]:
    return (
        pd.read_csv(path),
        pd.read_csv(path, header=1),
    )


def _read_excel_candidates(path: Path) -> tuple[pd.DataFrame, ...]:
    try:
        return (
            pd.read_excel(path, header=1),
            pd.read_excel(path, header=0),
        )
    except ImportError as exc:
        raise ImportError(
            "Reading the official UCI .xls file requires xlrd. Install project "
            "dependencies again with `.venv\\Scripts\\python -m pip install -e .`."
        ) from exc


def load_uci_default_benchmark(path: str | Path = DEFAULT_UCI_DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Load and normalize the UCI Default of Credit Card Clients dataset."""

    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(
            "UCI benchmark data was not found. Download the official file from "
            f"{UCI_DEFAULT_DATASET_PAGE} and place it at '{DEFAULT_UCI_DEFAULT_DATA_PATH}', "
            "or pass --benchmark-data with the local CSV/XLS path."
        )

    suffix = data_path.suffix.lower()
    if suffix in {".xls", ".xlsx"}:
        candidates = _read_excel_candidates(data_path)
    elif suffix == ".csv":
        candidates = _read_csv_candidates(data_path)
    else:
        raise ValueError("UCI benchmark data must be a .csv, .xls, or .xlsx file.")

    errors: list[str] = []
    for candidate in candidates:
        try:
            return normalize_uci_default_frame(candidate)
        except ValueError as exc:
            errors.append(str(exc))

    raise ValueError(
        "Could not normalize the UCI benchmark file. Tried common CSV/XLS header "
        f"layouts. Last errors: {' | '.join(errors)}"
    )


def _round_for_report(frame: pd.DataFrame, digits: int = 4) -> pd.DataFrame:
    result = frame.copy()
    numeric_columns = result.select_dtypes(include="number").columns
    result[numeric_columns] = result[numeric_columns].round(digits)
    return result


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

        ax.set_title("UCI Credit Default Benchmark Calibration")
        ax.set_xlabel("Mean predicted default probability")
        ax.set_ylabel("Actual default rate")
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


def _write_summary(
    output_path: Path,
    *,
    model_metrics: pd.DataFrame,
    calibration: pd.DataFrame,
    top_features: pd.DataFrame,
    error_summary: pd.DataFrame,
    segment_errors: pd.DataFrame,
    artifacts: BenchmarkArtifactPaths,
) -> None:
    metric_columns = [
        "model",
        "test_roc_auc",
        "test_brier_score",
        "test_precision",
        "test_recall",
        "test_f1",
    ]
    feature_columns = ["model", "rank", "feature", "abs_value"]
    error_columns = [
        "error_type",
        "n",
        "share_of_test",
        "mean_high_risk_probability",
        "decision_meaning",
    ]
    segment_columns = [
        "segment_feature",
        "segment_value",
        "n",
        "false_positive_rate",
        "false_negative_rate",
    ]
    files = "\n".join(
        f"- `{path.name}`"
        for path in artifacts.files
        if path.name != output_path.name
    )
    summary_errors = error_summary[error_summary["error_type"].notna()]

    text = f"""# UCI Credit Default Benchmark Artifacts

Generated by:

```powershell
.venv\\Scripts\\python -m microscore --benchmark uci-default
```

Source: {UCI_DEFAULT_DATASET_PAGE}

This benchmark tests the MicroScore modeling pipeline on a real public
credit-risk dataset. It does not validate Pavlodar borrower geography or prove
readiness for Kazakhstan microfinance deployment.

## Files

{files}

## Model Metrics

{_markdown_table(model_metrics[metric_columns])}

## Calibration Preview

{_markdown_table(calibration.head(12))}

## Top Features

{_markdown_table(top_features[feature_columns], max_rows=20)}

## Error Analysis Summary

{_markdown_table(summary_errors[error_columns])}

## Segment Error Preview

{_markdown_table(segment_errors[segment_columns], max_rows=16)}
"""
    output_path.write_text(text, encoding="utf-8")


def run_uci_default_benchmark(
    data_path: str | Path = DEFAULT_UCI_DEFAULT_DATA_PATH,
    *,
    frame: pd.DataFrame | None = None,
    output_dir: str | Path = DEFAULT_BENCHMARK_REPORTS_DIR,
    model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
    n_bins: int = 10,
) -> BenchmarkArtifactPaths:
    """Run the UCI Default of Credit Card Clients benchmark experiment."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    benchmark_frame = (
        normalize_uci_default_frame(frame)
        if frame is not None
        else load_uci_default_benchmark(data_path)
    )
    factories = model_factories or build_models(random_state)

    X, y = make_model_frame(
        benchmark_frame,
        target=TARGET_COLUMN,
        drop_columns=UCI_ID_COLUMNS,
        engineer_features=False,
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    results = [
        evaluate_model(
            model_name,
            model_factory(),
            X_train,
            X_test,
            y_train,
            y_test,
            random_state=random_state,
        )
        for model_name, model_factory in factories.items()
    ]

    calibration_tables = []
    feature_tables = []
    for result in results:
        y_probability = result.estimator.predict_proba(X_test)[:, 1]
        model_calibration = calibration_table(y_test, y_probability, n_bins=n_bins)
        model_calibration.insert(0, "model", result.name)
        calibration_tables.append(model_calibration)

        features = result.feature_importance.head(20).copy()
        features.insert(0, "model", result.name)
        features.insert(1, "rank", np.arange(1, len(features) + 1))
        feature_tables.append(features)

    model_metrics = results_table(results)
    calibration = pd.concat(calibration_tables, ignore_index=True)
    top_features = pd.concat(feature_tables, ignore_index=True)
    error_analysis = run_error_analysis(
        frame=benchmark_frame,
        drop_columns=UCI_ID_COLUMNS,
        engineer_features=False,
        segment_columns=UCI_SEGMENT_COLUMNS,
        example_columns=UCI_EXAMPLE_COLUMNS,
        min_group_size=20,
        random_state=random_state,
        test_size=test_size,
    )

    paths = BenchmarkArtifactPaths(
        output_dir=output_path,
        summary_markdown=output_path / "SUMMARY.md",
        manifest_json=output_path / "manifest.json",
        model_metrics_csv=output_path / "model_metrics.csv",
        calibration_csv=output_path / "calibration_bins.csv",
        top_features_csv=output_path / "top_features.csv",
        error_summary_csv=output_path / "error_analysis_summary.csv",
        segment_error_csv=output_path / "segment_error_analysis.csv",
        false_positive_examples_csv=output_path / "false_positive_examples.csv",
        false_negative_examples_csv=output_path / "false_negative_examples.csv",
        plot_paths=(),
    )

    _round_for_report(model_metrics).to_csv(paths.model_metrics_csv, index=False)
    _round_for_report(calibration).to_csv(paths.calibration_csv, index=False)
    _round_for_report(top_features).to_csv(paths.top_features_csv, index=False)
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

    plot_paths = tuple(
        path
        for path in (
            _write_calibration_plot(calibration, output_path / "calibration_curve.png"),
        )
        if path is not None
    )
    paths = BenchmarkArtifactPaths(
        output_dir=paths.output_dir,
        summary_markdown=paths.summary_markdown,
        manifest_json=paths.manifest_json,
        model_metrics_csv=paths.model_metrics_csv,
        calibration_csv=paths.calibration_csv,
        top_features_csv=paths.top_features_csv,
        error_summary_csv=paths.error_summary_csv,
        segment_error_csv=paths.segment_error_csv,
        false_positive_examples_csv=paths.false_positive_examples_csv,
        false_negative_examples_csv=paths.false_negative_examples_csv,
        plot_paths=plot_paths,
    )

    manifest = {
        "project": "MicroScore",
        "benchmark": "UCI Default of Credit Card Clients",
        "source": UCI_DEFAULT_DATASET_PAGE,
        "rows": int(len(benchmark_frame)),
        "target": TARGET_COLUMN,
        "random_state": random_state,
        "test_size": test_size,
        "n_bins": n_bins,
        "files": [path.name for path in paths.files],
        "data_warning": (
            "Public Taiwan credit-card default benchmark; not Pavlodar MFI data "
            "and not evidence of Kazakhstan deployment readiness."
        ),
    }
    paths.manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_summary(
        paths.summary_markdown,
        model_metrics=model_metrics,
        calibration=calibration,
        top_features=top_features,
        error_summary=error_analysis.summary,
        segment_errors=error_analysis.segment_errors,
        artifacts=paths,
    )
    return paths
