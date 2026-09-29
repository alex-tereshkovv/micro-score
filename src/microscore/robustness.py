"""Robustness and uncertainty diagnostics for MicroScore models.

This module deliberately separates model uncertainty from the portfolio-level
Monte Carlo simulator.  It asks whether the fitted score remains stable when
the train/test split changes, when the held-out sample is resampled, and when
plausible-but-synthetic input shifts are applied.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import DEFAULT_DROP_COLUMNS, TARGET_COLUMN, make_model_frame
from .modeling import RANDOM_STATE, build_models

DEFAULT_SPLIT_SEEDS = (7, 19, 42, 73, 101, 137, 211, 307, 401, 509)
DEFAULT_BOOTSTRAP_ITERATIONS = 1_000
DEFAULT_CONFIDENCE_LEVEL = 0.95

BASELINE_SCENARIO = "leakage_safe_baseline"
THIN_FILE_SCENARIO = "no_late_payment_count"

SHIFT_SCENARIOS = (
    "baseline",
    "digital_access_contraction",
    "affordability_pressure",
    "repayment_history_missing",
)


@dataclass(frozen=True)
class RobustnessReport:
    """Tables produced by the model robustness suite."""

    split_runs: pd.DataFrame
    split_summary: pd.DataFrame
    bootstrap_intervals: pd.DataFrame
    covariate_shift: pd.DataFrame


def _drop_columns_for_scenario(scenario: str) -> tuple[str, ...]:
    if scenario == BASELINE_SCENARIO:
        return DEFAULT_DROP_COLUMNS
    if scenario == THIN_FILE_SCENARIO:
        return (*DEFAULT_DROP_COLUMNS, "late_payment_count")
    raise ValueError(f"Unknown robustness scenario: {scenario}")


def _classification_metrics(
    y_true: pd.Series | np.ndarray,
    probability: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    prediction = (probability >= threshold).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_true, probability)),
        "brier_score": float(brier_score_loss(y_true, probability)),
        "accuracy": float(accuracy_score(y_true, prediction)),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
    }


def bootstrap_metric_intervals(
    y_true: pd.Series | np.ndarray,
    probability: np.ndarray,
    *,
    iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Return stratified bootstrap intervals for ROC-AUC and Brier score.

    Sampling positives and negatives separately guarantees that every bootstrap
    replicate contains both classes, so the ROC-AUC is always defined.
    """

    if iterations < 50:
        raise ValueError("iterations must be at least 50")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")

    labels = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probability, dtype=float)
    if labels.shape[0] != probabilities.shape[0]:
        raise ValueError("y_true and probability must have the same length")
    if not np.isfinite(probabilities).all():
        raise ValueError("probability contains non-finite values")

    negative_indices = np.flatnonzero(labels == 0)
    positive_indices = np.flatnonzero(labels == 1)
    if len(negative_indices) == 0 or len(positive_indices) == 0:
        raise ValueError("both target classes are required for bootstrap intervals")

    rng = np.random.default_rng(random_state)
    roc_auc_values = np.empty(iterations, dtype=float)
    brier_values = np.empty(iterations, dtype=float)

    for index in range(iterations):
        sampled_indices = np.concatenate(
            (
                rng.choice(negative_indices, size=len(negative_indices), replace=True),
                rng.choice(positive_indices, size=len(positive_indices), replace=True),
            )
        )
        sampled_labels = labels[sampled_indices]
        sampled_probabilities = probabilities[sampled_indices]
        roc_auc_values[index] = roc_auc_score(sampled_labels, sampled_probabilities)
        brier_values[index] = brier_score_loss(sampled_labels, sampled_probabilities)

    alpha = (1 - confidence_level) / 2
    rows = []
    for metric, point_estimate, samples in (
        ("roc_auc", roc_auc_score(labels, probabilities), roc_auc_values),
        ("brier_score", brier_score_loss(labels, probabilities), brier_values),
    ):
        lower, upper = np.quantile(samples, [alpha, 1 - alpha])
        rows.append(
            {
                "metric": metric,
                "point_estimate": float(point_estimate),
                "ci_lower": float(lower),
                "ci_upper": float(upper),
                "interval_width": float(upper - lower),
                "confidence_level": confidence_level,
                "bootstrap_iterations": iterations,
            }
        )
    return pd.DataFrame(rows)


def run_repeated_split_stability(
    frame: pd.DataFrame,
    *,
    model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    random_states: Iterable[int] = DEFAULT_SPLIT_SEEDS,
    test_size: float = 0.2,
) -> pd.DataFrame:
    """Evaluate baseline and thin-file ablation across repeated splits."""

    seeds = tuple(int(seed) for seed in random_states)
    if len(seeds) < 2:
        raise ValueError("at least two random states are required")

    rows: list[dict[str, float | int | str]] = []
    for seed in seeds:
        factories = model_factories or build_models(seed)
        for scenario in (BASELINE_SCENARIO, THIN_FILE_SCENARIO):
            X, y = make_model_frame(
                frame,
                target=TARGET_COLUMN,
                drop_columns=_drop_columns_for_scenario(scenario),
            )
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=test_size,
                random_state=seed,
                stratify=y,
            )

            for model_name, model_factory in factories.items():
                estimator = clone(model_factory())
                estimator.fit(X_train, y_train)
                probability = estimator.predict_proba(X_test)[:, 1]
                row: dict[str, float | int | str] = {
                    "scenario": scenario,
                    "model": model_name,
                    "split_seed": seed,
                    "test_rows": len(y_test),
                    "test_high_risk_rate": float(y_test.mean()),
                }
                row.update(_classification_metrics(y_test, probability))
                rows.append(row)

    return pd.DataFrame(rows)


def summarize_split_stability(split_runs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate repeated-split runs into reviewer-friendly intervals."""

    required = {"scenario", "model", "split_seed", "roc_auc", "brier_score"}
    missing = required.difference(split_runs.columns)
    if missing:
        raise ValueError(f"split_runs is missing columns: {sorted(missing)}")

    rows = []
    for (scenario, model), group in split_runs.groupby(["scenario", "model"], sort=False):
        roc_auc = group["roc_auc"]
        brier = group["brier_score"]
        rows.append(
            {
                "scenario": scenario,
                "model": model,
                "runs": int(len(group)),
                "roc_auc_mean": float(roc_auc.mean()),
                "roc_auc_std": float(roc_auc.std(ddof=1)),
                "roc_auc_min": float(roc_auc.min()),
                "roc_auc_max": float(roc_auc.max()),
                "roc_auc_p025": float(roc_auc.quantile(0.025)),
                "roc_auc_p975": float(roc_auc.quantile(0.975)),
                "brier_score_mean": float(brier.mean()),
                "brier_score_std": float(brier.std(ddof=1)),
            }
        )
    return pd.DataFrame(rows)


def apply_covariate_shift(frame: pd.DataFrame, scenario: str) -> pd.DataFrame:
    """Apply a deterministic, synthetic stress to raw held-out inputs."""

    if scenario not in SHIFT_SCENARIOS:
        raise ValueError(f"Unknown covariate-shift scenario: {scenario}")

    shifted = frame.copy(deep=True)
    if scenario == "baseline":
        return shifted

    if scenario == "digital_access_contraction":
        for column in ("mobile_banking_logins", "online_transfer_frequency"):
            if column in shifted:
                shifted[column] = shifted[column] * 0.40
        if "atm_withdrawal_frequency" in shifted:
            shifted["atm_withdrawal_frequency"] = shifted["atm_withdrawal_frequency"] * 1.20
        return shifted

    if scenario == "affordability_pressure":
        for column in ("annual_income", "avg_monthly_balance", "avg_deposit_amount"):
            if column in shifted:
                shifted[column] = shifted[column] * 0.75
        for column in ("total_outstanding_debt", "loan_application_amount"):
            if column in shifted:
                shifted[column] = shifted[column] * 1.15
        return shifted

    if "late_payment_count" in shifted:
        shifted["late_payment_count"] = np.nan
    return shifted


def run_covariate_shift_stress(
    frame: pd.DataFrame,
    *,
    model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> pd.DataFrame:
    """Measure score movement under deterministic held-out input stresses."""

    X, y = make_model_frame(frame, target=TARGET_COLUMN, drop_columns=DEFAULT_DROP_COLUMNS)
    train_indices, test_indices = train_test_split(
        frame.index,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )
    X_train = X.loc[train_indices]
    y_train = y.loc[train_indices]
    y_test = y.loc[test_indices]
    factories = model_factories or build_models(random_state)
    rows: list[dict[str, float | int | str]] = []

    for model_name, model_factory in factories.items():
        estimator = clone(model_factory())
        estimator.fit(X_train, y_train)
        baseline_probability = estimator.predict_proba(X.loc[test_indices])[:, 1]
        baseline_metrics = _classification_metrics(y_test, baseline_probability)

        for scenario in SHIFT_SCENARIOS:
            shifted_raw = apply_covariate_shift(frame.loc[test_indices], scenario)
            shifted_X, _ = make_model_frame(
                shifted_raw,
                target=TARGET_COLUMN,
                drop_columns=DEFAULT_DROP_COLUMNS,
            )
            shifted_X = shifted_X.reindex(columns=X.columns)
            probability = estimator.predict_proba(shifted_X)[:, 1]
            metrics = _classification_metrics(y_test, probability)
            absolute_shift = np.abs(probability - baseline_probability)
            rows.append(
                {
                    "model": model_name,
                    "scenario": scenario,
                    "test_rows": len(y_test),
                    **metrics,
                    "delta_roc_auc_vs_baseline": metrics["roc_auc"]
                    - baseline_metrics["roc_auc"],
                    "delta_brier_vs_baseline": metrics["brier_score"]
                    - baseline_metrics["brier_score"],
                    "mean_high_risk_probability": float(probability.mean()),
                    "mean_abs_probability_shift": float(absolute_shift.mean()),
                    "p95_abs_probability_shift": float(np.quantile(absolute_shift, 0.95)),
                    "classification_flip_rate": float(
                        np.mean(
                            (probability >= 0.5)
                            != (baseline_probability >= 0.5)
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


def run_robustness_suite(
    frame: pd.DataFrame,
    *,
    model_factories: dict[str, Callable[[], Pipeline]] | None = None,
    random_states: Iterable[int] = DEFAULT_SPLIT_SEEDS,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    random_state: int = RANDOM_STATE,
    test_size: float = 0.2,
) -> RobustnessReport:
    """Run the complete deterministic robustness suite."""

    split_runs = run_repeated_split_stability(
        frame,
        model_factories=model_factories,
        random_states=random_states,
        test_size=test_size,
    )
    split_summary = summarize_split_stability(split_runs)

    bootstrap_rows = []
    factories = model_factories or build_models(random_state)
    for scenario in (BASELINE_SCENARIO, THIN_FILE_SCENARIO):
        X, y = make_model_frame(
            frame,
            target=TARGET_COLUMN,
            drop_columns=_drop_columns_for_scenario(scenario),
        )
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=y,
        )
        for model_offset, (model_name, model_factory) in enumerate(factories.items()):
            estimator = clone(model_factory())
            estimator.fit(X_train, y_train)
            probability = estimator.predict_proba(X_test)[:, 1]
            intervals = bootstrap_metric_intervals(
                y_test,
                probability,
                iterations=bootstrap_iterations,
                confidence_level=confidence_level,
                random_state=random_state + model_offset,
            )
            intervals.insert(0, "model", model_name)
            intervals.insert(0, "scenario", scenario)
            bootstrap_rows.append(intervals)

    covariate_shift = run_covariate_shift_stress(
        frame,
        model_factories=model_factories,
        random_state=random_state,
        test_size=test_size,
    )
    return RobustnessReport(
        split_runs=split_runs,
        split_summary=split_summary,
        bootstrap_intervals=pd.concat(bootstrap_rows, ignore_index=True),
        covariate_shift=covariate_shift,
    )
