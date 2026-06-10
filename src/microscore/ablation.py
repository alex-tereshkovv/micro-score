"""Feature-group ablation experiments for MicroScore."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import (
    DEFAULT_DROP_COLUMNS,
    IDENTIFIER_COLUMNS,
    LEAKAGE_COLUMNS,
    TARGET_COLUMN,
    make_model_frame,
)
from .modeling import (
    RANDOM_STATE,
    build_models,
    build_preprocessor,
    evaluate_model,
    load_dataset,
    results_table,
)
from .paths import DEFAULT_DATA_PATH
from .regional import add_pavlodar_regional_context


BEHAVIORAL_SOURCE_COLUMNS: tuple[str, ...] = (
    "annual_income",
    "account_age_months",
    "avg_monthly_balance",
    "num_deposits_per_month",
    "avg_deposit_amount",
    "debit_card_usage_frequency",
    "debit_card_spending",
    "mobile_banking_logins",
    "online_transfer_frequency",
    "atm_withdrawal_frequency",
    "num_open_loans",
    "total_outstanding_debt",
    "loan_application_amount",
)

REGIONAL_COLUMNS: tuple[str, ...] = (
    "pavlodar_district",
    "settlement_type",
    "distance_to_pavlodar_km",
    "regional_digital_access_index",
    "regional_income_index",
    "mfi_branch_access_index",
    "seasonal_income_risk",
    "financial_access_gap",
    "rural_flag",
)

BASELINE_SCENARIO = "no_leakage_baseline"


@dataclass(frozen=True)
class AblationScenario:
    """Definition of one feature-group comparison."""

    name: str
    description: str
    source_columns: tuple[str, ...] | None = None
    drop_columns: tuple[str, ...] = DEFAULT_DROP_COLUMNS
    use_regional_context: bool = False
    engineer_features: bool = True
    notes: str = ""


def ablation_scenarios() -> tuple[AblationScenario, ...]:
    """Return the standard MicroScore ablation study design."""

    behavioral_plus_regional = BEHAVIORAL_SOURCE_COLUMNS + REGIONAL_COLUMNS

    return (
        AblationScenario(
            name="all_features_raw",
            description="All available columns except identifiers.",
            drop_columns=IDENTIFIER_COLUMNS,
            notes="Diagnostic ceiling; intentionally keeps traditional/leakage-like fields.",
        ),
        AblationScenario(
            name=BASELINE_SCENARIO,
            description="Default model with identifier and leakage columns removed.",
            drop_columns=DEFAULT_DROP_COLUMNS,
        ),
        AblationScenario(
            name="no_late_payment_count",
            description="Default leakage-safe model without late_payment_count.",
            drop_columns=DEFAULT_DROP_COLUMNS + ("late_payment_count",),
            notes="Thin-file stress test for the strongest repayment-history proxy.",
        ),
        AblationScenario(
            name="behavioral_only",
            description="Behavioral and financial activity signals only.",
            source_columns=BEHAVIORAL_SOURCE_COLUMNS,
            drop_columns=(),
            notes="Excludes demographics, repayment-history proxy, and regional assumptions.",
        ),
        AblationScenario(
            name="regional_only",
            description="Pavlodar regional scaffold only.",
            source_columns=REGIONAL_COLUMNS,
            drop_columns=(),
            use_regional_context=True,
            notes="Tests whether regional assumptions alone carry predictive signal.",
        ),
        AblationScenario(
            name="behavioral_plus_regional",
            description="Behavioral signals plus the Pavlodar regional scaffold.",
            source_columns=behavioral_plus_regional,
            drop_columns=(),
            use_regional_context=True,
            notes="Thin-file scenario without late_payment_count or leakage columns.",
        ),
    )


def build_ablation_models(
    random_state: int = RANDOM_STATE,
) -> dict[str, Callable[[], Pipeline]]:
    """Return models for research comparisons, including a no-skill baseline."""

    return {
        "Dummy Classifier": lambda: Pipeline(
            steps=[
                ("preprocess", build_preprocessor()),
                (
                    "model",
                    DummyClassifier(
                        strategy="stratified",
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        **build_models(random_state),
    }


def _select_existing_columns(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    target: str,
) -> pd.DataFrame:
    selected = [target, *[column for column in columns if column in frame.columns]]
    return frame.loc[:, selected].copy()


def _frame_for_scenario(
    frame: pd.DataFrame,
    scenario: AblationScenario,
    *,
    target: str,
    random_state: int,
) -> pd.DataFrame:
    scenario_frame = (
        add_pavlodar_regional_context(frame, random_state=random_state)
        if scenario.use_regional_context
        else frame.copy()
    )

    if scenario.source_columns is None:
        return scenario_frame

    return _select_existing_columns(scenario_frame, scenario.source_columns, target=target)


def _evaluate_scenario(
    frame: pd.DataFrame,
    scenario: AblationScenario,
    *,
    target: str,
    random_state: int,
    test_size: float,
    model_factories: dict[str, Callable[[], Pipeline]],
) -> pd.DataFrame:
    scenario_frame = _frame_for_scenario(
        frame,
        scenario,
        target=target,
        random_state=random_state,
    )
    X, y = make_model_frame(
        scenario_frame,
        target=target,
        drop_columns=scenario.drop_columns,
        engineer_features=scenario.engineer_features,
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
        for model_name, model_factory in model_factories.items()
    ]

    table = results_table(results)
    feature_columns = set(X.columns)
    table.insert(0, "scenario", scenario.name)
    table.insert(1, "description", scenario.description)
    table.insert(2, "feature_count", len(feature_columns))
    table.insert(3, "uses_regional_context", scenario.use_regional_context)
    table.insert(
        4,
        "includes_late_payment_count",
        "late_payment_count" in feature_columns,
    )
    table.insert(
        5,
        "includes_leakage_columns",
        bool(feature_columns.intersection(LEAKAGE_COLUMNS)),
    )
    table.insert(6, "notes", scenario.notes)
    return table


def _add_baseline_deltas(
    table: pd.DataFrame,
    *,
    baseline_scenario: str = BASELINE_SCENARIO,
) -> pd.DataFrame:
    result = table.copy()
    baseline_rows = result[result["scenario"] == baseline_scenario].set_index("model")
    metrics = ("test_roc_auc", "test_brier_score", "test_f1", "test_recall")

    for metric in metrics:
        delta_column = f"delta_{metric}_vs_no_leakage"
        result[delta_column] = result.apply(
            lambda row: (
                row[metric] - baseline_rows.loc[row["model"], metric]
                if row["model"] in baseline_rows.index and metric in result.columns
                else pd.NA
            ),
            axis=1,
        )

    return result


def run_ablation_study(
    data_path: str | Path = DEFAULT_DATA_PATH,
    *,
    frame: pd.DataFrame | None = None,
    target: str = TARGET_COLUMN,
    scenarios: tuple[AblationScenario, ...] | None = None,
    model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> pd.DataFrame:
    """Run feature-group ablations and return one comparison table."""

    base_frame = frame.copy() if frame is not None else load_dataset(data_path)
    scenario_definitions = scenarios or ablation_scenarios()
    factories = model_factories or build_ablation_models(random_state)

    tables = [
        _evaluate_scenario(
            base_frame,
            scenario,
            target=target,
            random_state=random_state,
            test_size=test_size,
            model_factories=factories,
        )
        for scenario in scenario_definitions
    ]
    combined = pd.concat(tables, ignore_index=True)
    return _add_baseline_deltas(combined)
