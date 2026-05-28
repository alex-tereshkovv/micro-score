"""Credit decision-threshold analysis for MicroScore."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .modeling import RANDOM_STATE, build_logistic_regression


@dataclass
class DecisionReport:
    model_quality: pd.DataFrame
    threshold_table: pd.DataFrame
    best_threshold: float
    best_threshold_metrics: pd.DataFrame
    segment_approval: pd.DataFrame


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def threshold_decision_table(
    y_true: pd.Series,
    y_probability: np.ndarray,
    loan_amount: pd.Series,
    *,
    thresholds: np.ndarray | None = None,
    interest_margin: float = 0.22,
    loss_given_default: float = 0.65,
) -> pd.DataFrame:
    """Estimate approval/default/profit trade-offs for risk thresholds.

    `credit_risk=1` is treated as a high-risk/default-like outcome. A borrower
    is approved when predicted high-risk probability is less than or equal to
    the threshold.
    """

    if thresholds is None:
        thresholds = np.round(np.arange(0.05, 0.96, 0.05), 2)

    y_array = np.asarray(y_true).astype(int)
    probabilities = np.asarray(y_probability, dtype=float)
    amounts = np.asarray(loan_amount, dtype=float)

    rows: list[dict[str, float]] = []
    for threshold in thresholds:
        approved = probabilities <= threshold
        approved_count = int(approved.sum())
        approved_defaults = int(((y_array == 1) & approved).sum())
        approved_good = int(((y_array == 0) & approved).sum())

        profit = np.where(
            approved & (y_array == 0),
            amounts * interest_margin,
            np.where(approved & (y_array == 1), -amounts * loss_given_default, 0.0),
        )

        rows.append(
            {
                "threshold": float(threshold),
                "approval_rate": float(approved.mean()),
                "approved_count": approved_count,
                "default_rate_among_approved": _safe_divide(approved_defaults, approved_count),
                "good_borrower_rejection_rate": _safe_divide(
                    int(((y_array == 0) & ~approved).sum()),
                    int((y_array == 0).sum()),
                ),
                "bad_borrower_approval_rate": _safe_divide(
                    approved_defaults,
                    int((y_array == 1).sum()),
                ),
                "expected_profit_total": float(profit.sum()),
                "expected_profit_per_applicant": float(profit.mean()),
                "expected_profit_per_approved": _safe_divide(float(profit.sum()), approved_count),
                "approved_good_count": approved_good,
                "approved_high_risk_count": approved_defaults,
            }
        )

    return pd.DataFrame(rows)


def segment_approval_table(
    segments: pd.DataFrame,
    y_true: pd.Series,
    y_probability: np.ndarray,
    *,
    threshold: float,
    segment_columns: tuple[str, ...] = ("pavlodar_district", "settlement_type", "gender"),
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    frame = segments.copy()
    frame["y_true"] = np.asarray(y_true).astype(int)
    frame["approved"] = np.asarray(y_probability) <= threshold

    for column in segment_columns:
        if column not in frame.columns:
            continue
        for value, group in frame.groupby(column, dropna=False):
            approved = group["approved"].to_numpy()
            y_group = group["y_true"].to_numpy()
            approved_count = int(approved.sum())
            rows.append(
                {
                    "segment_feature": column,
                    "segment_value": str(value),
                    "n": int(len(group)),
                    "approval_rate": float(approved.mean()),
                    "actual_high_risk_rate": float(y_group.mean()),
                    "default_rate_among_approved": _safe_divide(
                        int(((y_group == 1) & approved).sum()),
                        approved_count,
                    ),
                    "good_borrower_rejection_rate": _safe_divide(
                        int(((y_group == 0) & ~approved).sum()),
                        int((y_group == 0).sum()),
                    ),
                }
            )

    return pd.DataFrame(rows).sort_values(["segment_feature", "segment_value"]).reset_index(drop=True)


def run_decision_analysis(
    frame: pd.DataFrame,
    *,
    estimator_factory: Callable[[int], Pipeline] = build_logistic_regression,
    model_name: str = "Logistic Regression",
    target: str = TARGET_COLUMN,
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
    loan_amount_column: str = "loan_application_amount",
    interest_margin: float = 0.22,
    loss_given_default: float = 0.65,
    segment_columns: tuple[str, ...] = ("pavlodar_district", "settlement_type", "gender"),
) -> DecisionReport:
    """Train a model and evaluate lending thresholds on the held-out test set."""

    if loan_amount_column not in frame.columns:
        raise ValueError(f"Loan amount column '{loan_amount_column}' is missing.")

    X, y = make_model_frame(frame, target=target, drop_columns=drop_columns)
    loan_amount = frame.loc[X.index, loan_amount_column]
    segments = frame.loc[X.index, [column for column in segment_columns if column in frame.columns]]

    X_train, X_test, y_train, y_test, _amount_train, amount_test, _seg_train, seg_test = train_test_split(
        X,
        y,
        loan_amount,
        segments,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    estimator = clone(estimator_factory(random_state))
    estimator.fit(X_train, y_train)
    y_probability = estimator.predict_proba(X_test)[:, 1]

    threshold_table = threshold_decision_table(
        y_test,
        y_probability,
        amount_test,
        interest_margin=interest_margin,
        loss_given_default=loss_given_default,
    )
    best_index = threshold_table["expected_profit_per_applicant"].idxmax()
    best_threshold = float(threshold_table.loc[best_index, "threshold"])
    best_threshold_metrics = threshold_table.loc[[best_index]].reset_index(drop=True)

    model_quality = pd.DataFrame(
        [
            {
                "model": model_name,
                "test_roc_auc": roc_auc_score(y_test, y_probability),
                "brier_score": brier_score_loss(y_test, y_probability),
                "interest_margin": interest_margin,
                "loss_given_default": loss_given_default,
            }
        ]
    )

    segment_approval = segment_approval_table(
        seg_test,
        y_test,
        y_probability,
        threshold=best_threshold,
        segment_columns=segment_columns,
    )

    return DecisionReport(
        model_quality=model_quality,
        threshold_table=threshold_table,
        best_threshold=best_threshold,
        best_threshold_metrics=best_threshold_metrics,
        segment_approval=segment_approval,
    )
