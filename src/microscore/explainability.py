"""Local explanation utilities for MicroScore models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

ExplanationDirection = Literal["increases_risk", "reduces_risk"]


@dataclass(frozen=True)
class LocalFactor:
    """One local additive factor for a single prediction."""

    feature: str
    value: float
    abs_value: float
    direction: ExplanationDirection
    label: str


@dataclass(frozen=True)
class LocalExplanation:
    """Additive local explanation for one scored application."""

    method: str
    baseline_log_odds: float
    total_contribution: float
    predicted_log_odds: float
    high_risk_probability: float
    top_positive_factors: list[LocalFactor]
    top_protective_factors: list[LocalFactor]
    top_factors: list[LocalFactor]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""

        return asdict(self)


def _clean_feature_names(feature_names: np.ndarray) -> list[str]:
    return [
        name.replace("num__", "").replace("cat__", "")
        for name in feature_names
    ]


def _risk_direction(value: float) -> ExplanationDirection:
    return "increases_risk" if value >= 0 else "reduces_risk"


def _risk_label(value: float) -> str:
    return "Raises predicted risk" if value >= 0 else "Lowers predicted risk"


def _is_missing_derived_feature(feature_name: str, missing_features: set[str]) -> bool:
    return any(
        feature_name == missing_feature or feature_name.startswith(f"{missing_feature}_")
        for missing_feature in missing_features
    )


def _factor_records(
    feature_names: list[str],
    contributions: np.ndarray,
    *,
    missing_features: set[str],
) -> pd.DataFrame:
    factor_frame = pd.DataFrame(
        {
            "feature": feature_names,
            "value": contributions,
            "abs_value": np.abs(contributions),
        }
    )
    factor_frame = factor_frame[
        (factor_frame["abs_value"] > 1e-9)
        & ~factor_frame["feature"].map(
            lambda name: _is_missing_derived_feature(name, missing_features)
        )
    ].copy()
    factor_frame["direction"] = factor_frame["value"].map(_risk_direction)
    factor_frame["label"] = factor_frame["value"].map(_risk_label)
    return factor_frame


def _to_factors(frame: pd.DataFrame) -> list[LocalFactor]:
    return [
        LocalFactor(
            feature=str(row["feature"]),
            value=float(row["value"]),
            abs_value=float(row["abs_value"]),
            direction=row["direction"],
            label=row["label"],
        )
        for row in frame.to_dict(orient="records")
    ]


def logistic_local_explanation(
    estimator: Any,
    input_frame: pd.DataFrame,
    missing_features: list[str] | None = None,
    *,
    limit: int = 8,
) -> LocalExplanation:
    """Explain a Logistic Regression prediction as additive log-odds factors.

    For the current API model, this is exact after preprocessing:
    intercept + sum(transformed_feature * coefficient) equals the predicted
    log-odds. It is intentionally lightweight and dependency-free. Future
    tree-based or nonlinear models should use SHAP/TreeSHAP.
    """

    preprocessor = estimator.named_steps["preprocess"]
    model = estimator.named_steps["model"]

    if not hasattr(model, "coef_") or not hasattr(model, "intercept_"):
        raise TypeError("logistic_local_explanation requires a fitted linear model.")

    transformed = preprocessor.transform(input_frame)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()

    feature_names = _clean_feature_names(preprocessor.get_feature_names_out())
    contributions = np.asarray(transformed)[0] * model.coef_[0]
    baseline_log_odds = float(model.intercept_[0])
    total_contribution = float(contributions.sum())
    predicted_log_odds = float(baseline_log_odds + total_contribution)
    high_risk_probability = float(1.0 / (1.0 + np.exp(-predicted_log_odds)))

    factor_frame = _factor_records(
        feature_names,
        contributions,
        missing_features=set(missing_features or []),
    )
    top_factors = factor_frame.sort_values("abs_value", ascending=False).head(limit)
    top_positive = (
        factor_frame[factor_frame["value"] > 0]
        .sort_values("value", ascending=False)
        .head(limit)
    )
    top_protective = (
        factor_frame[factor_frame["value"] < 0]
        .sort_values("value", ascending=True)
        .head(limit)
    )

    return LocalExplanation(
        method="logistic_regression_additive_log_odds",
        baseline_log_odds=baseline_log_odds,
        total_contribution=total_contribution,
        predicted_log_odds=predicted_log_odds,
        high_risk_probability=high_risk_probability,
        top_positive_factors=_to_factors(top_positive),
        top_protective_factors=_to_factors(top_protective),
        top_factors=_to_factors(top_factors),
    )
