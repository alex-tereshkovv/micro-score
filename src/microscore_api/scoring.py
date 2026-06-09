"""Scoring service used by the optional MicroScore API prototype."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from microscore.features import add_behavioral_features, make_model_frame
from microscore.modeling import (
    RANDOM_STATE,
    build_logistic_regression,
    feature_importance,
    load_dataset,
)
from microscore.regional import add_pavlodar_regional_context


@dataclass(frozen=True)
class ScoreResult:
    model_name: str
    model_version: str
    high_risk_probability: float
    risk_band: str
    missing_feature_count: int
    missing_features_preview: list[str]
    top_model_factors: list[dict[str, object]]
    warnings: list[str]


def risk_band(probability: float) -> str:
    if probability < 0.35:
        return "low"
    if probability < 0.65:
        return "medium"
    return "high"


def _importance_records(importance: pd.DataFrame, limit: int = 8) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    value_columns = [column for column in importance.columns if column not in {"feature", "abs_value"}]
    value_column = value_columns[0] if value_columns else "abs_value"

    for row in importance.head(limit).to_dict(orient="records"):
        records.append(
            {
                "feature": str(row["feature"]),
                "value": float(row[value_column]),
                "abs_value": float(row["abs_value"]),
            }
        )
    return records


class ScoringService:
    """Train-on-start scoring service for the first product prototype.

    This is intentionally simple: it trains the current research model on the
    synthetic dataset and exposes a reusable `score` method. A production
    version should load a reviewed, versioned model artifact instead.
    """

    def __init__(
        self,
        *,
        model_name: str = "Logistic Regression",
        model_version: str = "research-v0.1",
        random_state: int = RANDOM_STATE,
    ) -> None:
        frame = add_pavlodar_regional_context(load_dataset(), random_state=random_state)
        X, y = make_model_frame(frame)

        estimator = build_logistic_regression(random_state=random_state)
        estimator.fit(X, y)

        self.model_name = model_name
        self.model_version = model_version
        self.estimator = estimator
        self.expected_columns = list(X.columns)
        self.training_dtypes = X.dtypes.to_dict()
        self.top_model_factors = _importance_records(feature_importance(estimator))

    def _build_input_frame(self, features: dict[str, Any]) -> tuple[pd.DataFrame, list[str]]:
        raw = pd.DataFrame([features])
        engineered = add_behavioral_features(raw)

        row: dict[str, Any] = {}
        missing_features: list[str] = []
        for column in self.expected_columns:
            value = engineered[column].iloc[0] if column in engineered.columns else np.nan
            if pd.isna(value):
                missing_features.append(column)

            if is_numeric_dtype(self.training_dtypes[column]):
                value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            elif value is None:
                value = np.nan

            row[column] = value

        return pd.DataFrame([row], columns=self.expected_columns), missing_features

    def score(self, features: dict[str, Any]) -> ScoreResult:
        input_frame, missing_features = self._build_input_frame(features)
        probability = float(self.estimator.predict_proba(input_frame)[0, 1])

        warnings: list[str] = []
        if missing_features:
            warnings.append(
                "Some model features were missing and were handled by the preprocessing pipeline."
            )
        if "late_payment_count" in features:
            warnings.append(
                "late_payment_count is a strong proxy feature in the current synthetic dataset."
            )
        else:
            warnings.append(
                "No late_payment_count was supplied; this is closer to a thin-file borrower scenario."
            )

        return ScoreResult(
            model_name=self.model_name,
            model_version=self.model_version,
            high_risk_probability=probability,
            risk_band=risk_band(probability),
            missing_feature_count=len(missing_features),
            missing_features_preview=missing_features[:12],
            top_model_factors=self.top_model_factors,
            warnings=warnings,
        )


@lru_cache(maxsize=1)
def get_scoring_service() -> ScoringService:
    return ScoringService()

