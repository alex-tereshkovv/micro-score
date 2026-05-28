"""Proxy-feature and segment audits for MicroScore models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .modeling import (
    DEFAULT_DATA_PATH,
    RANDOM_STATE,
    build_logistic_regression,
    build_models,
    evaluate_model,
    load_dataset,
    results_table,
)


@dataclass
class AuditReport:
    proxy_summary: pd.DataFrame
    proxy_by_value: pd.DataFrame
    feature_drop_comparison: pd.DataFrame
    segment_metrics: pd.DataFrame


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def proxy_feature_audit(
    frame: pd.DataFrame,
    *,
    feature: str = "late_payment_count",
    target: str = TARGET_COLUMN,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure whether one feature is strong enough to behave like a proxy."""

    if feature not in frame.columns:
        raise ValueError(f"Feature column '{feature}' is missing from the dataset.")
    if target not in frame.columns:
        raise ValueError(f"Target column '{target}' is missing from the dataset.")

    y = frame[target].astype(int)
    score = frame[feature].astype(float)
    by_value = (
        frame.groupby(feature, dropna=False)
        .agg(
            n=(target, "size"),
            high_risk_rate=(target, "mean"),
        )
        .reset_index()
        .sort_values(feature)
    )

    auc = roc_auc_score(y, score)
    correlation = frame[[feature, target]].corr(method="spearman").loc[feature, target]
    min_rate = by_value["high_risk_rate"].min()
    max_rate = by_value["high_risk_rate"].max()

    if auc >= 0.8 or (max_rate - min_rate) >= 0.5:
        strength = "high"
    elif auc >= 0.7 or (max_rate - min_rate) >= 0.3:
        strength = "moderate"
    else:
        strength = "low"

    summary = pd.DataFrame(
        [
            {
                "feature": feature,
                "single_feature_roc_auc": auc,
                "spearman_corr": correlation,
                "min_group_high_risk_rate": min_rate,
                "max_group_high_risk_rate": max_rate,
                "risk_rate_spread": max_rate - min_rate,
                "proxy_strength": strength,
            }
        ]
    )

    return summary, by_value


def _evaluate_models_on_frame(
    frame: pd.DataFrame,
    *,
    scenario: str,
    drop_columns: tuple[str, ...],
    target: str = TARGET_COLUMN,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> pd.DataFrame:
    X, y = make_model_frame(frame, target=target, drop_columns=drop_columns)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    results = [
        evaluate_model(
            name,
            model_factory(),
            X_train,
            X_test,
            y_train,
            y_test,
            random_state=random_state,
        )
        for name, model_factory in build_models(random_state).items()
    ]
    table = results_table(results)
    table.insert(0, "scenario", scenario)
    return table


def compare_with_without_feature(
    frame: pd.DataFrame,
    *,
    feature: str = "late_payment_count",
    target: str = TARGET_COLUMN,
    base_drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Compare model metrics before and after dropping a suspected proxy feature."""

    without_feature_drop = tuple(dict.fromkeys((*base_drop_columns, feature)))
    with_feature = _evaluate_models_on_frame(
        frame,
        scenario=f"with_{feature}",
        drop_columns=base_drop_columns,
        target=target,
        random_state=random_state,
    )
    without_feature = _evaluate_models_on_frame(
        frame,
        scenario=f"without_{feature}",
        drop_columns=without_feature_drop,
        target=target,
        random_state=random_state,
    )
    comparison = pd.concat([with_feature, without_feature], ignore_index=True)

    metric_columns = [column for column in comparison.columns if column.startswith("test_")]
    baseline = comparison[comparison["scenario"] == f"with_{feature}"].set_index("model")
    for index, row in comparison.iterrows():
        model = row["model"]
        for metric in metric_columns:
            comparison.loc[index, f"delta_{metric}"] = row[metric] - baseline.loc[model, metric]

    return comparison


def segment_metrics_from_predictions(
    segments: pd.DataFrame,
    y_true: pd.Series,
    y_pred: np.ndarray,
    y_probability: np.ndarray,
    *,
    segment_columns: tuple[str, ...] = ("gender", "employment_status"),
    model_name: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    evaluation_frame = segments.copy()
    evaluation_frame["y_true"] = np.asarray(y_true)
    evaluation_frame["y_pred"] = y_pred
    evaluation_frame["y_probability"] = y_probability

    for column in segment_columns:
        if column not in evaluation_frame.columns:
            continue

        for value, group in evaluation_frame.groupby(column, dropna=False):
            y_group = group["y_true"].to_numpy()
            pred_group = group["y_pred"].to_numpy()
            prob_group = group["y_probability"].to_numpy()

            tn = int(((y_group == 0) & (pred_group == 0)).sum())
            fp = int(((y_group == 0) & (pred_group == 1)).sum())
            fn = int(((y_group == 1) & (pred_group == 0)).sum())
            tp = int(((y_group == 1) & (pred_group == 1)).sum())

            rows.append(
                {
                    "model": model_name,
                    "segment_feature": column,
                    "segment_value": str(value),
                    "n": int(len(group)),
                    "actual_high_risk_rate": float(y_group.mean()),
                    "predicted_high_risk_rate": float(pred_group.mean()),
                    "mean_predicted_probability": float(prob_group.mean()),
                    "accuracy": accuracy_score(y_group, pred_group),
                    "precision": precision_score(y_group, pred_group, zero_division=0),
                    "recall": recall_score(y_group, pred_group, zero_division=0),
                    "f1": f1_score(y_group, pred_group, zero_division=0),
                    "false_positive_rate": _safe_divide(fp, fp + tn),
                    "false_negative_rate": _safe_divide(fn, fn + tp),
                }
            )

    return pd.DataFrame(rows).sort_values(["segment_feature", "segment_value"]).reset_index(drop=True)


def evaluate_segments(
    frame: pd.DataFrame,
    *,
    estimator_factory: Callable[[int], Pipeline] = build_logistic_regression,
    model_name: str = "Logistic Regression",
    segment_columns: tuple[str, ...] = ("gender", "employment_status"),
    target: str = TARGET_COLUMN,
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> pd.DataFrame:
    """Evaluate predictions across borrower segments on the held-out test set."""

    X, y = make_model_frame(frame, target=target, drop_columns=drop_columns)
    segments = frame.loc[X.index, [column for column in segment_columns if column in frame.columns]]
    X_train, X_test, y_train, y_test, _segments_train, segments_test = train_test_split(
        X,
        y,
        segments,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    estimator = clone(estimator_factory(random_state))
    estimator.fit(X_train, y_train)
    y_pred = estimator.predict(X_test)
    y_probability = estimator.predict_proba(X_test)[:, 1]

    return segment_metrics_from_predictions(
        segments_test,
        y_test,
        y_pred,
        y_probability,
        segment_columns=segment_columns,
        model_name=model_name,
    )


def run_audit(
    data_path: str | Path = DEFAULT_DATA_PATH,
    *,
    proxy_feature: str = "late_payment_count",
    segment_columns: tuple[str, ...] = ("gender", "employment_status"),
    random_state: int = RANDOM_STATE,
) -> AuditReport:
    frame = load_dataset(data_path)
    proxy_summary, proxy_by_value = proxy_feature_audit(
        frame,
        feature=proxy_feature,
    )
    feature_drop_comparison = compare_with_without_feature(
        frame,
        feature=proxy_feature,
        random_state=random_state,
    )
    segment_metrics = evaluate_segments(
        frame,
        segment_columns=segment_columns,
        random_state=random_state,
    )

    return AuditReport(
        proxy_summary=proxy_summary,
        proxy_by_value=proxy_by_value,
        feature_drop_comparison=feature_drop_comparison,
        segment_metrics=segment_metrics,
    )
