"""Feature engineering for the MicroScore credit-risk dataset."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

TARGET_COLUMN = "credit_risk"

IDENTIFIER_COLUMNS = ("customer_id",)

# These fields either identify clients, represent traditional credit-score data,
# or are too close to the outcome to be realistic behavioral predictors.
LEAKAGE_COLUMNS = (
    "credit_score",
    "loan_default_history",
    "fraud_flag",
)

DEFAULT_DROP_COLUMNS = IDENTIFIER_COLUMNS + LEAKAGE_COLUMNS


def _has_columns(frame: pd.DataFrame, columns: Iterable[str]) -> bool:
    return all(column in frame.columns for column in columns)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    ratio = numerator / denominator
    return ratio.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_behavioral_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add derived behavioral and financial-pressure features.

    The function is defensive: if a future dataset lacks one of the source
    columns, the related derived feature is skipped instead of failing.
    """

    result = frame.copy()

    if _has_columns(result, ("annual_income", "total_outstanding_debt")):
        result["income_to_debt_ratio"] = _safe_ratio(
            result["annual_income"],
            result["total_outstanding_debt"] + 1.0,
        )

    if _has_columns(
        result,
        (
            "mobile_banking_logins",
            "online_transfer_frequency",
            "atm_withdrawal_frequency",
        ),
    ):
        result["digital_activity_score"] = (
            result["mobile_banking_logins"]
            + result["online_transfer_frequency"]
            + result["atm_withdrawal_frequency"]
        )

    if _has_columns(result, ("avg_deposit_amount", "debit_card_spending")):
        result["deposit_to_spending_ratio"] = _safe_ratio(
            result["avg_deposit_amount"],
            result["debit_card_spending"] + 1.0,
        )

    if _has_columns(result, ("loan_application_amount", "annual_income")):
        result["loan_to_income_ratio"] = _safe_ratio(
            result["loan_application_amount"],
            result["annual_income"] + 1.0,
        )

    if _has_columns(
        result,
        ("loan_application_amount", "total_outstanding_debt", "annual_income"),
    ):
        result["total_credit_pressure"] = _safe_ratio(
            result["loan_application_amount"] + result["total_outstanding_debt"],
            result["annual_income"] + 1.0,
        )

    if _has_columns(result, ("total_outstanding_debt", "num_open_loans")):
        result["debt_per_open_loan"] = _safe_ratio(
            result["total_outstanding_debt"],
            result["num_open_loans"] + 1.0,
        )

    return result


def make_model_frame(
    frame: pd.DataFrame,
    *,
    target: str = TARGET_COLUMN,
    drop_columns: Iterable[str] = DEFAULT_DROP_COLUMNS,
    engineer_features: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Return a feature matrix and target vector ready for sklearn pipelines."""

    if target not in frame.columns:
        raise ValueError(f"Target column '{target}' is missing from the dataset.")

    data = add_behavioral_features(frame) if engineer_features else frame.copy()
    columns_to_drop = [target, *drop_columns]
    features = data.drop(columns=columns_to_drop, errors="ignore")
    target_values = data[target].astype(int)

    leaked_columns = sorted(set(drop_columns).intersection(features.columns))
    if leaked_columns:
        raise ValueError(f"Leakage columns remained in features: {leaked_columns}")

    return features, target_values
