"""Scoring service used by the optional MicroScore API prototype."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from microscore.explainability import LocalExplanation, logistic_local_explanation
from microscore.features import DEFAULT_DROP_COLUMNS, add_behavioral_features, make_model_frame
from microscore.modeling import (
    RANDOM_STATE,
    build_logistic_regression,
    load_dataset,
)
from microscore.regional import add_pavlodar_regional_context, district_profile_table


@dataclass(frozen=True)
class ScenarioScore:
    scenario: str
    label: str
    high_risk_probability: float
    risk_band: str
    notes: list[str]


@dataclass(frozen=True)
class DecisionSupport:
    recommendation_code: str
    title: str
    rationale: list[str]
    next_steps: list[str]


@dataclass(frozen=True)
class ScoreResult:
    model_name: str
    model_version: str
    high_risk_probability: float
    risk_band: str
    proxy_sensitivity_delta: float
    scenario_scores: list[ScenarioScore]
    decision_support: DecisionSupport
    missing_feature_count: int
    missing_features_preview: list[str]
    explanation: LocalExplanation
    top_model_factors: list[dict[str, object]]
    warnings: list[str]


def risk_band(probability: float) -> str:
    if probability < 0.35:
        return "low"
    if probability < 0.65:
        return "medium"
    return "high"


def _decision_support(
    standard_score: ScenarioScore,
    thin_file_score: ScenarioScore,
    proxy_sensitivity_delta: float,
    missing_feature_count: int,
) -> DecisionSupport:
    rationale = [
        f"Standard risk is {standard_score.risk_band} ({standard_score.high_risk_probability:.1%}).",
        f"Thin-file risk is {thin_file_score.risk_band} ({thin_file_score.high_risk_probability:.1%}).",
    ]
    if missing_feature_count:
        rationale.append(f"{missing_feature_count} expected model features were not supplied.")

    if proxy_sensitivity_delta >= 0.25:
        rationale.append(
            f"Proxy sensitivity is high ({proxy_sensitivity_delta:.1%}); late-payment history changes the score materially."
        )
        return DecisionSupport(
            recommendation_code="manual_review_proxy_sensitive",
            title="Manual review - proxy-sensitive score",
            rationale=rationale,
            next_steps=[
                "Verify the context behind late payments before making a decision.",
                "Request additional behavioral or income-stability evidence.",
                "Do not use this score as an automatic decline.",
            ],
        )

    if (
        standard_score.high_risk_probability < 0.35
        and thin_file_score.high_risk_probability < 0.55
    ):
        return DecisionSupport(
            recommendation_code="starter_loan_candidate",
            title="Candidate for small starter loan",
            rationale=rationale,
            next_steps=[
                "Consider a small first loan with conservative exposure.",
                "Use repayment behavior to update future credit limits.",
                "Keep human approval in the loop.",
            ],
        )

    if (
        standard_score.high_risk_probability >= 0.75
        and thin_file_score.high_risk_probability >= 0.65
    ):
        return DecisionSupport(
            recommendation_code="high_risk_review",
            title="High risk - additional review required",
            rationale=rationale,
            next_steps=[
                "Request additional documentation or guarantor information.",
                "Consider restructuring loan size or term.",
                "Escalate to a senior analyst before approval.",
            ],
        )

    return DecisionSupport(
        recommendation_code="standard_manual_review",
        title="Manual review",
        rationale=rationale,
        next_steps=[
            "Review borrower context and application purpose.",
            "Compare score with affordability and income-stability evidence.",
            "Choose a threshold policy before making a decision.",
        ],
    )


def _add_known_regional_fields(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "pavlodar_district" not in result.columns:
        return result

    district = result["pavlodar_district"].iloc[0]
    if pd.isna(district):
        return result

    profiles = district_profile_table()
    matches = profiles[profiles["district"] == district]
    if matches.empty:
        return result

    profile = matches.iloc[0]
    regional_values = {
        "settlement_type": profile["settlement_type"],
        "distance_to_pavlodar_km": profile["distance_to_pavlodar_km"],
        "regional_digital_access_index": profile["digital_access_index"],
        "regional_income_index": profile["income_index"],
        "mfi_branch_access_index": profile["mfi_branch_access_index"],
        "seasonal_income_risk": profile["seasonal_income_risk"],
        "financial_access_gap": 1.0
        - (
            0.55 * profile["digital_access_index"]
            + 0.45 * profile["mfi_branch_access_index"]
        ),
        "rural_flag": int(profile["settlement_type"] == "rural"),
    }
    for column, value in regional_values.items():
        if column not in result.columns or pd.isna(result[column].iloc[0]):
            result[column] = value
    return result


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
        X_thin_file, y_thin_file = make_model_frame(
            frame,
            drop_columns=(*DEFAULT_DROP_COLUMNS, "late_payment_count"),
        )

        estimator = build_logistic_regression(random_state=random_state)
        estimator.fit(X, y)

        thin_file_estimator = build_logistic_regression(random_state=random_state)
        thin_file_estimator.fit(X_thin_file, y_thin_file)

        self.model_name = model_name
        self.model_version = model_version
        self.estimator = estimator
        self.expected_columns = list(X.columns)
        self.training_dtypes = X.dtypes.to_dict()
        self.thin_file_estimator = thin_file_estimator
        self.thin_file_expected_columns = list(X_thin_file.columns)
        self.thin_file_training_dtypes = X_thin_file.dtypes.to_dict()

    def _build_input_frame(
        self,
        features: dict[str, Any],
        *,
        expected_columns: list[str],
        training_dtypes: dict[str, Any],
    ) -> tuple[pd.DataFrame, list[str]]:
        raw = _add_known_regional_fields(pd.DataFrame([features]))
        engineered = add_behavioral_features(raw)

        row: dict[str, Any] = {}
        missing_features: list[str] = []
        for column in expected_columns:
            value = engineered[column].iloc[0] if column in engineered.columns else np.nan
            if pd.isna(value):
                missing_features.append(column)

            if is_numeric_dtype(training_dtypes[column]):
                value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            elif value is None:
                value = np.nan

            row[column] = value

        return pd.DataFrame([row], columns=expected_columns), missing_features

    def _scenario_score(
        self,
        *,
        estimator: Any,
        input_frame: pd.DataFrame,
        scenario: str,
        label: str,
        notes: list[str],
    ) -> ScenarioScore:
        probability = float(estimator.predict_proba(input_frame)[0, 1])
        return ScenarioScore(
            scenario=scenario,
            label=label,
            high_risk_probability=probability,
            risk_band=risk_band(probability),
            notes=notes,
        )

    def score(self, features: dict[str, Any]) -> ScoreResult:
        input_frame, missing_features = self._build_input_frame(
            features,
            expected_columns=self.expected_columns,
            training_dtypes=self.training_dtypes,
        )
        thin_file_input_frame, thin_file_missing_features = self._build_input_frame(
            {key: value for key, value in features.items() if key != "late_payment_count"},
            expected_columns=self.thin_file_expected_columns,
            training_dtypes=self.thin_file_training_dtypes,
        )

        standard_score = self._scenario_score(
            estimator=self.estimator,
            input_frame=input_frame,
            scenario="standard",
            label="Standard model",
            notes=["Uses the current research feature set, including late payment history when supplied."],
        )
        thin_file_score = self._scenario_score(
            estimator=self.thin_file_estimator,
            input_frame=thin_file_input_frame,
            scenario="thin_file_without_late_payment_count",
            label="Thin-file model",
            notes=["Drops late_payment_count to test how robust the score is without the strongest proxy feature."],
        )
        probability = standard_score.high_risk_probability
        proxy_sensitivity_delta = abs(
            standard_score.high_risk_probability - thin_file_score.high_risk_probability
        )
        decision_support = _decision_support(
            standard_score,
            thin_file_score,
            proxy_sensitivity_delta,
            len(missing_features),
        )
        explanation = logistic_local_explanation(
            self.estimator,
            input_frame,
            missing_features,
        )
        local_factors = [
            {
                "feature": factor.feature,
                "value": factor.value,
                "abs_value": factor.abs_value,
                "direction": factor.direction,
                "label": factor.label,
            }
            for factor in explanation.top_factors
        ]

        warnings: list[str] = []
        if missing_features:
            warnings.append(
                "Some model features were missing and were handled by the preprocessing pipeline."
            )
        if thin_file_missing_features:
            warnings.append(
                "Thin-file scenario also handled missing features through the preprocessing pipeline."
            )
        if "late_payment_count" in features:
            warnings.append(
                "late_payment_count is a strong proxy feature in the current synthetic dataset."
            )
        else:
            warnings.append(
                "No late_payment_count was supplied; this is closer to a thin-file borrower scenario."
            )
        if proxy_sensitivity_delta >= 0.2:
            warnings.append(
                "Risk estimate is sensitive to late_payment_count; review the thin-file scenario before deciding."
            )

        return ScoreResult(
            model_name=self.model_name,
            model_version=self.model_version,
            high_risk_probability=probability,
            risk_band=risk_band(probability),
            proxy_sensitivity_delta=proxy_sensitivity_delta,
            scenario_scores=[standard_score, thin_file_score],
            decision_support=decision_support,
            missing_feature_count=len(missing_features),
            missing_features_preview=missing_features[:12],
            explanation=explanation,
            top_model_factors=local_factors,
            warnings=warnings,
        )


@lru_cache(maxsize=1)
def get_scoring_service() -> ScoringService:
    return ScoringService()
