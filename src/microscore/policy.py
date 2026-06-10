"""Approval/review/decline policy analysis for MicroScore."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .modeling import (
    DEFAULT_DATA_PATH,
    RANDOM_STATE,
    build_logistic_regression,
    load_dataset,
)


DEFAULT_POLICY_SEGMENTS: tuple[str, ...] = (
    "gender",
    "employment_status",
    "settlement_type",
    "pavlodar_district",
)


@dataclass(frozen=True)
class ThresholdPolicy:
    """Three-zone decision policy for predicted high-risk probability."""

    name: str
    approve_threshold: float
    decline_threshold: float
    description: str


@dataclass(frozen=True)
class PolicyAnalysisReport:
    """Policy-level and segment-level decision trade-off tables."""

    policy_table: pd.DataFrame
    segment_policy_table: pd.DataFrame


def default_threshold_policies() -> tuple[ThresholdPolicy, ...]:
    """Return standard MicroScore policy scenarios."""

    return (
        ThresholdPolicy(
            name="lender_protective",
            approve_threshold=0.15,
            decline_threshold=0.50,
            description="Strict risk control; many applicants move to review or decline.",
        ),
        ThresholdPolicy(
            name="balanced_review",
            approve_threshold=0.35,
            decline_threshold=0.70,
            description="Middle policy with a substantial manual-review band.",
        ),
        ThresholdPolicy(
            name="inclusion_first",
            approve_threshold=0.50,
            decline_threshold=0.85,
            description="Higher access; only very high-risk applicants are auto-declined.",
        ),
        ThresholdPolicy(
            name="starter_loan_review",
            approve_threshold=0.25,
            decline_threshold=0.80,
            description="Small-starter-loan posture with wide review before decline.",
        ),
    )


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def _validate_policy(policy: ThresholdPolicy) -> None:
    if not 0 <= policy.approve_threshold <= 1:
        raise ValueError("approve_threshold must be between 0 and 1")
    if not 0 <= policy.decline_threshold <= 1:
        raise ValueError("decline_threshold must be between 0 and 1")
    if policy.approve_threshold >= policy.decline_threshold:
        raise ValueError("approve_threshold must be lower than decline_threshold")


def _policy_actions(probabilities: np.ndarray, policy: ThresholdPolicy) -> np.ndarray:
    _validate_policy(policy)
    return np.where(
        probabilities <= policy.approve_threshold,
        "approve",
        np.where(probabilities >= policy.decline_threshold, "decline", "review"),
    )


def _profit_for_actions(
    actions: np.ndarray,
    y_true: np.ndarray,
    amounts: np.ndarray,
    *,
    interest_margin: float,
    loss_given_default: float,
) -> np.ndarray:
    return np.where(
        (actions == "approve") & (y_true == 0),
        amounts * interest_margin,
        np.where((actions == "approve") & (y_true == 1), -amounts * loss_given_default, 0.0),
    )


def policy_decision_table(
    y_true: pd.Series,
    y_probability: np.ndarray,
    loan_amount: pd.Series,
    *,
    policies: tuple[ThresholdPolicy, ...] | None = None,
    interest_margin: float = 0.22,
    loss_given_default: float = 0.65,
) -> pd.DataFrame:
    """Compare approve/review/decline policies on held-out predictions."""

    policy_set = policies or default_threshold_policies()
    y_array = np.asarray(y_true).astype(int)
    probabilities = np.asarray(y_probability, dtype=float)
    amounts = np.asarray(loan_amount, dtype=float)
    n = len(y_array)
    good_total = int((y_array == 0).sum())
    high_risk_total = int((y_array == 1).sum())

    rows: list[dict[str, object]] = []
    for policy in policy_set:
        actions = _policy_actions(probabilities, policy)
        approved = actions == "approve"
        reviewed = actions == "review"
        declined = actions == "decline"
        approved_high_risk = int((approved & (y_array == 1)).sum())
        approved_good = int((approved & (y_array == 0)).sum())
        declined_good = int((declined & (y_array == 0)).sum())
        declined_high_risk = int((declined & (y_array == 1)).sum())
        profit = _profit_for_actions(
            actions,
            y_array,
            amounts,
            interest_margin=interest_margin,
            loss_given_default=loss_given_default,
        )

        rows.append(
            {
                "policy": policy.name,
                "description": policy.description,
                "approve_threshold": policy.approve_threshold,
                "decline_threshold": policy.decline_threshold,
                "n": n,
                "auto_approve_count": int(approved.sum()),
                "manual_review_count": int(reviewed.sum()),
                "auto_decline_count": int(declined.sum()),
                "auto_approval_rate": float(approved.mean()),
                "manual_review_rate": float(reviewed.mean()),
                "auto_decline_rate": float(declined.mean()),
                "high_risk_rate_among_approved": _safe_divide(
                    approved_high_risk,
                    int(approved.sum()),
                ),
                "high_risk_approval_rate": _safe_divide(
                    approved_high_risk,
                    high_risk_total,
                ),
                "good_borrower_auto_decline_rate": _safe_divide(
                    declined_good,
                    good_total,
                ),
                "approved_good_count": approved_good,
                "approved_high_risk_count": approved_high_risk,
                "declined_good_count": declined_good,
                "declined_high_risk_count": declined_high_risk,
                "expected_profit_auto_approved_total": float(profit.sum()),
                "expected_profit_per_applicant": float(profit.mean()),
                "expected_profit_per_auto_approved": _safe_divide(
                    float(profit.sum()),
                    int(approved.sum()),
                ),
            }
        )

    return pd.DataFrame(rows)


def segment_policy_table(
    segments: pd.DataFrame,
    y_true: pd.Series,
    y_probability: np.ndarray,
    *,
    policies: tuple[ThresholdPolicy, ...] | None = None,
    segment_columns: tuple[str, ...] = DEFAULT_POLICY_SEGMENTS,
    min_group_size: int = 10,
) -> pd.DataFrame:
    """Report policy actions by borrower segment."""

    policy_set = policies or default_threshold_policies()
    frame = segments.copy()
    frame["actual_credit_risk"] = np.asarray(y_true).astype(int)
    frame["high_risk_probability"] = np.asarray(y_probability, dtype=float)

    rows: list[dict[str, object]] = []
    for policy in policy_set:
        frame["policy_action"] = _policy_actions(
            frame["high_risk_probability"].to_numpy(),
            policy,
        )
        for column in segment_columns:
            if column not in frame.columns:
                continue
            for value, group in frame.groupby(column, dropna=False):
                if len(group) < min_group_size:
                    continue

                y_group = group["actual_credit_risk"].to_numpy()
                actions = group["policy_action"].to_numpy()
                approved = actions == "approve"
                reviewed = actions == "review"
                declined = actions == "decline"
                good_total = int((y_group == 0).sum())
                high_risk_total = int((y_group == 1).sum())

                rows.append(
                    {
                        "policy": policy.name,
                        "segment_feature": column,
                        "segment_value": str(value),
                        "n": int(len(group)),
                        "actual_high_risk_rate": float(group["actual_credit_risk"].mean()),
                        "auto_approval_rate": float(approved.mean()),
                        "manual_review_rate": float(reviewed.mean()),
                        "auto_decline_rate": float(declined.mean()),
                        "high_risk_approval_rate": _safe_divide(
                            int(((y_group == 1) & approved).sum()),
                            high_risk_total,
                        ),
                        "good_borrower_auto_decline_rate": _safe_divide(
                            int(((y_group == 0) & declined).sum()),
                            good_total,
                        ),
                        "mean_high_risk_probability": float(
                            group["high_risk_probability"].mean()
                        ),
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "policy",
                "segment_feature",
                "segment_value",
                "n",
                "actual_high_risk_rate",
                "auto_approval_rate",
                "manual_review_rate",
                "auto_decline_rate",
                "high_risk_approval_rate",
                "good_borrower_auto_decline_rate",
                "mean_high_risk_probability",
            ]
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["policy", "segment_feature", "segment_value"])
        .reset_index(drop=True)
    )


def run_policy_analysis(
    data_path: str | Path = DEFAULT_DATA_PATH,
    *,
    frame: pd.DataFrame | None = None,
    estimator_factory: Callable[[int], Pipeline] = build_logistic_regression,
    model_name: str = "Logistic Regression",
    target: str = TARGET_COLUMN,
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
    loan_amount_column: str = "loan_application_amount",
    policies: tuple[ThresholdPolicy, ...] | None = None,
    segment_columns: tuple[str, ...] = DEFAULT_POLICY_SEGMENTS,
    min_group_size: int = 10,
    interest_margin: float = 0.22,
    loss_given_default: float = 0.65,
) -> PolicyAnalysisReport:
    """Train the scoring model and compare three-zone decision policies."""

    source_frame = frame.copy() if frame is not None else load_dataset(data_path)
    if loan_amount_column not in source_frame.columns:
        raise ValueError(f"Loan amount column '{loan_amount_column}' is missing.")

    X, y = make_model_frame(source_frame, target=target, drop_columns=drop_columns)
    loan_amount = source_frame.loc[X.index, loan_amount_column]
    segments = source_frame.loc[
        X.index,
        [column for column in segment_columns if column in source_frame.columns],
    ]

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

    policy_table = policy_decision_table(
        y_test,
        y_probability,
        amount_test,
        policies=policies,
        interest_margin=interest_margin,
        loss_given_default=loss_given_default,
    )
    policy_table.insert(0, "model", model_name)

    segment_table = segment_policy_table(
        seg_test,
        y_test,
        y_probability,
        policies=policies,
        segment_columns=segment_columns,
        min_group_size=min_group_size,
    )
    segment_table.insert(0, "model", model_name)

    return PolicyAnalysisReport(
        policy_table=policy_table,
        segment_policy_table=segment_table,
    )
