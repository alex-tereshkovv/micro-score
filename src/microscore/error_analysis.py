"""False-positive and false-negative analysis for MicroScore."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .modeling import (
    DEFAULT_DATA_PATH,
    RANDOM_STATE,
    build_logistic_regression,
    load_dataset,
)


DEFAULT_SEGMENT_COLUMNS: tuple[str, ...] = (
    "gender",
    "employment_status",
    "settlement_type",
    "pavlodar_district",
)

DEFAULT_EXAMPLE_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "age",
    "gender",
    "employment_status",
    "annual_income",
    "loan_application_amount",
    "total_outstanding_debt",
    "late_payment_count",
    "mobile_banking_logins",
    "online_transfer_frequency",
    "atm_withdrawal_frequency",
    "pavlodar_district",
    "settlement_type",
)


@dataclass(frozen=True)
class ErrorAnalysisReport:
    """Held-out prediction error analysis tables."""

    summary: pd.DataFrame
    segment_errors: pd.DataFrame
    false_positive_examples: pd.DataFrame
    false_negative_examples: pd.DataFrame
    all_predictions: pd.DataFrame


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def _error_type(actual: int, predicted: int) -> str:
    if actual == 0 and predicted == 1:
        return "false_positive"
    if actual == 1 and predicted == 0:
        return "false_negative"
    if actual == 1 and predicted == 1:
        return "true_positive"
    return "true_negative"


def _decision_meaning(error_type: str) -> str:
    meanings = {
        "false_positive": "Good borrower could be wrongly flagged as high risk.",
        "false_negative": "High-risk borrower could be missed by the model.",
        "true_positive": "High-risk borrower correctly flagged.",
        "true_negative": "Good borrower correctly not flagged.",
    }
    return meanings[error_type]


def _prediction_frame(
    source_frame: pd.DataFrame,
    test_indices: pd.Index,
    y_test: pd.Series,
    y_probability: np.ndarray,
    *,
    threshold: float,
    model_name: str,
    example_columns: tuple[str, ...],
) -> pd.DataFrame:
    predicted = (np.asarray(y_probability) >= threshold).astype(int)
    result = source_frame.loc[test_indices, [column for column in example_columns if column in source_frame.columns]].copy()
    result.insert(0, "row_index", test_indices.to_numpy())
    result.insert(1, "model", model_name)
    result["actual_credit_risk"] = np.asarray(y_test).astype(int)
    result["predicted_credit_risk"] = predicted
    result["high_risk_probability"] = np.asarray(y_probability, dtype=float)
    result["threshold"] = threshold
    result["probability_margin_from_threshold"] = (
        result["high_risk_probability"] - threshold
    ).abs()
    result["error_type"] = [
        _error_type(actual, prediction)
        for actual, prediction in zip(result["actual_credit_risk"], predicted)
    ]
    result["decision_meaning"] = result["error_type"].map(_decision_meaning)
    return result


def _summary_table(
    predictions: pd.DataFrame,
    *,
    model_name: str,
    threshold: float,
) -> pd.DataFrame:
    y_true = predictions["actual_credit_risk"].to_numpy()
    y_pred = predictions["predicted_credit_risk"].to_numpy()
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    n = len(predictions)

    counts = predictions["error_type"].value_counts()
    rows = [
        {
            "model": model_name,
            "threshold": threshold,
            "n": n,
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
            "false_positive_rate": _safe_divide(fp, fp + tn),
            "false_negative_rate": _safe_divide(fn, fn + tp),
            "false_discovery_rate": _safe_divide(fp, fp + tp),
            "false_omission_rate": _safe_divide(fn, fn + tn),
            "error_rate": _safe_divide(fp + fn, n),
        }
    ]

    for error_type in ("false_positive", "false_negative", "true_positive", "true_negative"):
        subset = predictions[predictions["error_type"] == error_type]
        rows.append(
            {
                "model": model_name,
                "threshold": threshold,
                "error_type": error_type,
                "n": int(counts.get(error_type, 0)),
                "share_of_test": _safe_divide(int(counts.get(error_type, 0)), n),
                "mean_high_risk_probability": float(subset["high_risk_probability"].mean())
                if not subset.empty
                else float("nan"),
                "mean_late_payment_count": float(subset["late_payment_count"].mean())
                if "late_payment_count" in subset.columns and not subset.empty
                else float("nan"),
                "mean_loan_application_amount": float(subset["loan_application_amount"].mean())
                if "loan_application_amount" in subset.columns and not subset.empty
                else float("nan"),
                "decision_meaning": _decision_meaning(error_type),
            }
        )

    return pd.DataFrame(rows)


def _segment_error_table(
    predictions: pd.DataFrame,
    *,
    segment_columns: tuple[str, ...],
    min_group_size: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in segment_columns:
        if column not in predictions.columns:
            continue

        for value, group in predictions.groupby(column, dropna=False):
            if len(group) < min_group_size:
                continue

            y_true = group["actual_credit_risk"].to_numpy()
            y_pred = group["predicted_credit_risk"].to_numpy()
            tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
            rows.append(
                {
                    "segment_feature": column,
                    "segment_value": str(value),
                    "n": int(len(group)),
                    "actual_high_risk_rate": float(group["actual_credit_risk"].mean()),
                    "predicted_high_risk_rate": float(group["predicted_credit_risk"].mean()),
                    "mean_high_risk_probability": float(group["high_risk_probability"].mean()),
                    "false_positive_count": int(fp),
                    "false_negative_count": int(fn),
                    "false_positive_rate": _safe_divide(fp, fp + tn),
                    "false_negative_rate": _safe_divide(fn, fn + tp),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "segment_feature",
                "segment_value",
                "n",
                "actual_high_risk_rate",
                "predicted_high_risk_rate",
                "mean_high_risk_probability",
                "false_positive_count",
                "false_negative_count",
                "false_positive_rate",
                "false_negative_rate",
            ]
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["segment_feature", "false_negative_rate", "false_positive_rate"], ascending=[True, False, False])
        .reset_index(drop=True)
    )


def _top_error_examples(
    predictions: pd.DataFrame,
    *,
    error_type: str,
    limit: int,
) -> pd.DataFrame:
    subset = predictions[predictions["error_type"] == error_type].copy()
    if subset.empty:
        return subset

    if error_type == "false_positive":
        subset = subset.sort_values("high_risk_probability", ascending=False)
    elif error_type == "false_negative":
        subset = subset.sort_values("high_risk_probability", ascending=True)
    else:
        subset = subset.sort_values("probability_margin_from_threshold", ascending=False)

    return subset.head(limit).reset_index(drop=True)


def run_error_analysis(
    data_path: str | Path = DEFAULT_DATA_PATH,
    *,
    frame: pd.DataFrame | None = None,
    estimator_factory: Callable[[int], Pipeline] = build_logistic_regression,
    model_name: str = "Logistic Regression",
    target: str = TARGET_COLUMN,
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    engineer_features: bool = True,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
    threshold: float = 0.5,
    segment_columns: tuple[str, ...] = DEFAULT_SEGMENT_COLUMNS,
    example_columns: tuple[str, ...] = DEFAULT_EXAMPLE_COLUMNS,
    example_limit: int = 25,
    min_group_size: int = 10,
) -> ErrorAnalysisReport:
    """Analyze false positives and false negatives on the held-out test set."""

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    source_frame = frame.copy() if frame is not None else load_dataset(data_path)
    X, y = make_model_frame(
        source_frame,
        target=target,
        drop_columns=drop_columns,
        engineer_features=engineer_features,
    )

    X_train, X_test, y_train, y_test, _idx_train, idx_test = train_test_split(
        X,
        y,
        X.index,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    estimator = clone(estimator_factory(random_state))
    estimator.fit(X_train, y_train)
    y_probability = estimator.predict_proba(X_test)[:, 1]

    predictions = _prediction_frame(
        source_frame,
        pd.Index(idx_test),
        y_test,
        y_probability,
        threshold=threshold,
        model_name=model_name,
        example_columns=example_columns,
    )
    summary = _summary_table(predictions, model_name=model_name, threshold=threshold)
    segment_errors = _segment_error_table(
        predictions,
        segment_columns=segment_columns,
        min_group_size=min_group_size,
    )
    false_positives = _top_error_examples(
        predictions,
        error_type="false_positive",
        limit=example_limit,
    )
    false_negatives = _top_error_examples(
        predictions,
        error_type="false_negative",
        limit=example_limit,
    )

    return ErrorAnalysisReport(
        summary=summary,
        segment_errors=segment_errors,
        false_positive_examples=false_positives,
        false_negative_examples=false_negatives,
        all_predictions=predictions.reset_index(drop=True),
    )
