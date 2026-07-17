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

from .features import (
    DEFAULT_DROP_COLUMNS,
    TARGET_COLUMN,
    add_behavioral_features,
    make_model_frame,
)
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
    proxy_monitoring: pd.DataFrame
    feature_drop_comparison: pd.DataFrame
    segment_metrics: pd.DataFrame


DEFAULT_PROXY_MONITOR_FEATURES: tuple[str, ...] = (
    "late_payment_count",
    "num_open_loans",
    "total_outstanding_debt",
    "loan_application_amount",
    "annual_income",
    "avg_monthly_balance",
    "mobile_banking_logins",
    "online_transfer_frequency",
    "atm_withdrawal_frequency",
    "digital_activity_score",
    "income_to_debt_ratio",
    "loan_to_income_ratio",
    "total_credit_pressure",
    "debt_per_open_loan",
)

PROXY_FEATURE_RATIONALES: dict[str, tuple[str, str]] = {
    "late_payment_count": (
        "repayment_history",
        "Strong repayment-history proxy; must be audited separately before thin-file claims.",
    ),
    "num_open_loans": (
        "debt_burden",
        "May reproduce access to formal credit rather than independent behavioral signal.",
    ),
    "total_outstanding_debt": (
        "debt_burden",
        "May track legacy indebtedness and repayment access rather than thin-file behavior.",
    ),
    "loan_application_amount": (
        "monetary_scale",
        "Prototype amount-unit feature; needs KZT calibration before monetary interpretation.",
    ),
    "annual_income": (
        "monetary_scale",
        "Prototype amount-unit affordability input; not verified KZT income.",
    ),
    "avg_monthly_balance": (
        "monetary_scale",
        "Prototype balance feature; may proxy wealth and account formalization.",
    ),
    "mobile_banking_logins": (
        "digital_access",
        "May proxy smartphone, internet, or branch access rather than borrower reliability.",
    ),
    "online_transfer_frequency": (
        "digital_access",
        "May proxy digital inclusion and account usage access.",
    ),
    "atm_withdrawal_frequency": (
        "digital_access",
        "May proxy cash dependency, branch access, or rural infrastructure.",
    ),
    "digital_activity_score": (
        "digital_access",
        "Derived digital activity feature; needs segment checks for access bias.",
    ),
    "income_to_debt_ratio": (
        "derived_affordability",
        "Derived prototype affordability ratio; depends on uncalibrated amount units.",
    ),
    "loan_to_income_ratio": (
        "derived_affordability",
        "Derived prototype affordability ratio; not a verified repayment-capacity measure.",
    ),
    "total_credit_pressure": (
        "derived_affordability",
        "Derived pressure ratio from prototype monetary fields.",
    ),
    "debt_per_open_loan": (
        "derived_affordability",
        "Derived debt concentration measure from prototype monetary fields.",
    ),
}


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


def _proxy_strength(single_feature_roc_auc: float, risk_rate_spread: float) -> str:
    directional_auc = max(single_feature_roc_auc, 1.0 - single_feature_roc_auc)
    if directional_auc >= 0.8 or risk_rate_spread >= 0.5:
        return "high"
    if directional_auc >= 0.7 or risk_rate_spread >= 0.3:
        return "moderate"
    return "low"


def _monitoring_action(proxy_strength: str) -> str:
    if proxy_strength == "high":
        return "must_review_before_real_data_or_kzt_claims"
    if proxy_strength == "moderate":
        return "track_in_artifacts_and_segment_reviews"
    return "monitor_for_drift"


def _monitoring_group_rates(
    clean: pd.DataFrame,
    *,
    feature: str,
    target: str,
    max_bins: int = 10,
) -> pd.DataFrame:
    if clean[feature].nunique(dropna=False) > max_bins:
        try:
            group_key = pd.qcut(clean[feature], q=max_bins, duplicates="drop")
        except ValueError:
            group_key = clean[feature]
    else:
        group_key = clean[feature]

    return (
        clean.assign(_monitoring_group=group_key)
        .groupby("_monitoring_group", dropna=False, observed=False)
        .agg(n=(target, "size"), high_risk_rate=(target, "mean"))
        .reset_index()
    )


def _monitoring_summary(
    clean: pd.DataFrame,
    *,
    feature: str,
    target: str,
) -> dict[str, float | str]:
    y = clean[target].astype(int)
    score = clean[feature].astype(float)
    by_group = _monitoring_group_rates(clean, feature=feature, target=target)

    auc = float(roc_auc_score(y, score))
    correlation = float(clean[[feature, target]].corr(method="spearman").loc[feature, target])
    min_rate = float(by_group["high_risk_rate"].min())
    max_rate = float(by_group["high_risk_rate"].max())
    spread = max_rate - min_rate
    strength = _proxy_strength(auc, spread)

    return {
        "feature": feature,
        "single_feature_roc_auc": auc,
        "spearman_corr": correlation,
        "min_group_high_risk_rate": min_rate,
        "max_group_high_risk_rate": max_rate,
        "risk_rate_spread": spread,
        "proxy_strength": strength,
    }


def proxy_monitoring_table(
    frame: pd.DataFrame,
    *,
    features: tuple[str, ...] = DEFAULT_PROXY_MONITOR_FEATURES,
    target: str = TARGET_COLUMN,
) -> pd.DataFrame:
    """Return a multi-feature proxy-monitoring table for research artifacts.

    This is a research guardrail, not a product decision rule. It scans the
    strongest known repayment-history, monetary-scale, affordability, and
    digital-access proxies so reports keep synthetic limitations visible.
    """

    if target not in frame.columns:
        raise ValueError(f"Target column '{target}' is missing from the dataset.")

    enriched = add_behavioral_features(frame)
    rows: list[dict[str, object]] = []
    strength_order = {"high": 0, "moderate": 1, "low": 2}

    for feature in features:
        if feature not in enriched.columns:
            continue

        clean = enriched[[feature, target]].copy()
        clean[feature] = pd.to_numeric(clean[feature], errors="coerce")
        clean = clean.dropna(subset=[feature, target])
        if clean[feature].nunique(dropna=False) < 2 or clean[target].nunique() < 2:
            continue

        row = _monitoring_summary(clean, feature=feature, target=target)
        single_auc = float(row["single_feature_roc_auc"])
        spread = float(row["risk_rate_spread"])
        directional_auc = max(single_auc, 1.0 - single_auc)
        strength = str(row["proxy_strength"])
        family, rationale = PROXY_FEATURE_RATIONALES.get(
            feature,
            ("unclassified", "Monitor for unexpected single-feature dominance."),
        )
        row.update(
            {
                "feature_family": family,
                "directional_roc_auc": directional_auc,
                "risk_direction": (
                    "higher_values_higher_risk"
                    if single_auc >= 0.5
                    else "higher_values_lower_risk"
                ),
                "proxy_strength": strength,
                "monitoring_action": _monitoring_action(strength),
                "rationale": rationale,
            }
        )
        rows.append(row)

    if not rows:
        return pd.DataFrame(
            columns=[
                "feature",
                "feature_family",
                "single_feature_roc_auc",
                "directional_roc_auc",
                "spearman_corr",
                "risk_rate_spread",
                "risk_direction",
                "proxy_strength",
                "monitoring_action",
                "rationale",
            ]
        )

    result = pd.DataFrame(rows)
    result["_strength_order"] = result["proxy_strength"].map(strength_order)
    return (
        result.sort_values(
            ["_strength_order", "directional_roc_auc", "risk_rate_spread"],
            ascending=[True, False, False],
        )
        .drop(columns=["_strength_order"])
        .reset_index(drop=True)
    )


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
    proxy_monitoring = proxy_monitoring_table(frame)
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
        proxy_monitoring=proxy_monitoring,
        feature_drop_comparison=feature_drop_comparison,
        segment_metrics=segment_metrics,
    )
