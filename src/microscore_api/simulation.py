"""Reproducible Monte Carlo portfolio simulation for MFI policy review."""

from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
from typing import Any

import numpy as np

from microscore.policy import ThresholdPolicy, default_threshold_policies


SCENARIO_LOG_ODDS_SHIFTS: dict[str, float] = {
    "baseline": 0.0,
    "adverse": 0.45,
    "severe": 0.90,
}
MAX_SIMULATION_CELLS = 20_000_000

SIMULATION_NOTE = (
    "Scenario-planning output only. Results depend on synthetic, unvalidated "
    "risk probabilities and user-supplied assumptions; they are not forecasts, "
    "regulatory capital estimates, or automatic lending decisions."
)


def _policy_by_name(name: str) -> ThresholdPolicy:
    policies = {policy.name: policy for policy in default_threshold_policies()}
    try:
        return policies[name]
    except KeyError as exc:
        raise ValueError(f"Unknown threshold policy: {name}") from exc


def _policy_actions(probabilities: np.ndarray, policy: ThresholdPolicy) -> np.ndarray:
    return np.where(
        probabilities <= policy.approve_threshold,
        "approve",
        np.where(probabilities >= policy.decline_threshold, "decline", "review"),
    )


def _distribution(values: np.ndarray) -> dict[str, float]:
    quantiles = np.quantile(values.astype(float), [0.05, 0.50, 0.95])
    return {
        "mean": float(np.mean(values)),
        "p05": float(quantiles[0]),
        "p50": float(quantiles[1]),
        "p95": float(quantiles[2]),
    }


def _mean_standard_error(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0
    return float(np.std(values.astype(float), ddof=1) / np.sqrt(values.size))


def _portfolio_arrays(
    applications: Iterable[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, list[str], int, str]:
    probabilities: list[float] = []
    amounts: list[float] = []
    model_versions: set[str] = set()
    application_count = 0
    fingerprint_records: list[dict[str, Any]] = []

    for application in applications:
        application_count += 1
        score = application.get("score_result") or {}
        probability = score.get("high_risk_probability")
        if probability is None:
            continue
        amount = float(application.get("requested_amount") or 0.0)
        if amount <= 0:
            continue
        probabilities.append(float(np.clip(float(probability), 1e-6, 1 - 1e-6)))
        amounts.append(amount)
        model_version = str(score.get("model_version") or "unknown")
        model_versions.add(model_version)
        fingerprint_records.append(
            {
                "application_id": str(application.get("id") or "unknown"),
                "requested_amount": amount,
                "high_risk_probability": probabilities[-1],
                "model_version": model_version,
                "scored_at": application.get("scored_at"),
            }
        )

    fingerprint_payload = json.dumps(
        sorted(fingerprint_records, key=lambda row: row["application_id"]),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    portfolio_fingerprint = hashlib.sha256(fingerprint_payload).hexdigest()

    return (
        np.asarray(probabilities, dtype=float),
        np.asarray(amounts, dtype=float),
        sorted(model_versions),
        application_count,
        portfolio_fingerprint,
    )


def simulate_portfolio(
    applications: Iterable[dict[str, Any]],
    *,
    iterations: int = 5_000,
    seed: int = 20_260_619,
    policy_name: str = "balanced_review",
    scenarios: tuple[str, ...] = ("baseline", "adverse", "severe"),
    review_approval_rate: float = 0.50,
    interest_margin_rate: float = 0.22,
    loss_given_default: float = 0.65,
    operating_cost_per_approved: float = 0.0,
    macro_volatility: float = 0.25,
    calibration_volatility: float = 0.15,
    chunk_size: int = 256,
) -> dict[str, Any]:
    """Simulate portfolio outcomes under paired baseline and stress scenarios."""

    if iterations < 1:
        raise ValueError("iterations must be positive")
    for name, value in (
        ("review_approval_rate", review_approval_rate),
        ("interest_margin_rate", interest_margin_rate),
        ("loss_given_default", loss_given_default),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
    if operating_cost_per_approved < 0:
        raise ValueError("operating_cost_per_approved cannot be negative")
    if macro_volatility < 0 or calibration_volatility < 0:
        raise ValueError("simulation volatility cannot be negative")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if not scenarios:
        raise ValueError("at least one stress scenario is required")
    scenario_names = tuple(dict.fromkeys(scenarios))
    unknown_scenarios = [
        scenario for scenario in scenario_names if scenario not in SCENARIO_LOG_ODDS_SHIFTS
    ]
    if unknown_scenarios:
        raise ValueError(f"Unknown stress scenarios: {', '.join(unknown_scenarios)}")

    (
        probabilities,
        amounts,
        model_versions,
        application_count,
        portfolio_fingerprint,
    ) = _portfolio_arrays(applications)
    if probabilities.size == 0:
        raise ValueError("Monte Carlo simulation requires at least one scored application")
    simulation_cells = iterations * int(probabilities.size)
    if simulation_cells > MAX_SIMULATION_CELLS:
        raise ValueError(
            "Simulation workload is too large; reduce iterations or portfolio size "
            f"below {MAX_SIMULATION_CELLS:,} borrower-iterations"
        )

    policy = _policy_by_name(policy_name)
    actions = _policy_actions(probabilities, policy)
    auto_approved = actions == "approve"
    reviewed = actions == "review"
    auto_declined = actions == "decline"
    base_logits = np.log(probabilities / (1.0 - probabilities))
    rng = np.random.default_rng(seed)

    result_arrays: dict[str, dict[str, np.ndarray]] = {
        scenario: {
            "approved_count": np.empty(iterations, dtype=float),
            "default_count": np.empty(iterations, dtype=float),
            "default_rate": np.empty(iterations, dtype=float),
            "approved_exposure": np.empty(iterations, dtype=float),
            "portfolio_result": np.empty(iterations, dtype=float),
            "result_per_approved": np.empty(iterations, dtype=float),
            "mean_stressed_probability": np.empty(iterations, dtype=float),
        }
        for scenario in scenario_names
    }

    for start in range(0, iterations, chunk_size):
        stop = min(iterations, start + chunk_size)
        size = stop - start
        macro_standard = rng.normal(size=size)
        calibration_standard = rng.normal(size=(size, probabilities.size))
        review_uniform = rng.random(size=(size, probabilities.size))
        default_uniform = rng.random(size=(size, probabilities.size))

        entered = np.broadcast_to(auto_approved, (size, probabilities.size)).copy()
        entered |= reviewed & (review_uniform < review_approval_rate)
        approved_count = entered.sum(axis=1)
        approved_exposure = (entered * amounts).sum(axis=1)

        for scenario in scenario_names:
            stressed_logits = (
                base_logits[None, :]
                + SCENARIO_LOG_ODDS_SHIFTS[scenario]
                + macro_volatility * macro_standard[:, None]
                + calibration_volatility * calibration_standard
            )
            stressed_probabilities = 1.0 / (
                1.0 + np.exp(-np.clip(stressed_logits, -30.0, 30.0))
            )
            defaulted = entered & (default_uniform < stressed_probabilities)
            default_count = defaulted.sum(axis=1)
            default_rate = np.divide(
                default_count,
                approved_count,
                out=np.zeros(size, dtype=float),
                where=approved_count > 0,
            )
            non_default_result = amounts * interest_margin_rate - operating_cost_per_approved
            default_result = -amounts * loss_given_default - operating_cost_per_approved
            portfolio_result = np.where(
                entered,
                np.where(defaulted, default_result, non_default_result),
                0.0,
            ).sum(axis=1)
            result_per_approved = np.divide(
                portfolio_result,
                approved_count,
                out=np.zeros(size, dtype=float),
                where=approved_count > 0,
            )

            arrays = result_arrays[scenario]
            arrays["approved_count"][start:stop] = approved_count
            arrays["default_count"][start:stop] = default_count
            arrays["default_rate"][start:stop] = default_rate
            arrays["approved_exposure"][start:stop] = approved_exposure
            arrays["portfolio_result"][start:stop] = portfolio_result
            arrays["result_per_approved"][start:stop] = result_per_approved
            arrays["mean_stressed_probability"][start:stop] = (
                stressed_probabilities.mean(axis=1)
            )

    scenario_results: list[dict[str, Any]] = []
    for scenario in scenario_names:
        arrays = result_arrays[scenario]
        portfolio_result = arrays["portfolio_result"]
        scenario_results.append(
            {
                "scenario": scenario,
                "log_odds_shift": SCENARIO_LOG_ODDS_SHIFTS[scenario],
                "approved_count": _distribution(arrays["approved_count"]),
                "default_count": _distribution(arrays["default_count"]),
                "default_rate": _distribution(arrays["default_rate"]),
                "approved_exposure": _distribution(arrays["approved_exposure"]),
                "portfolio_result": _distribution(portfolio_result),
                "result_per_approved": _distribution(arrays["result_per_approved"]),
                "mean_stressed_probability": float(
                    np.mean(arrays["mean_stressed_probability"])
                ),
                "probability_of_loss": float(np.mean(portfolio_result < 0.0)),
                "downside_p05": float(np.quantile(portfolio_result, 0.05)),
                "diagnostics": {
                    "portfolio_result_mean_standard_error": _mean_standard_error(
                        portfolio_result
                    ),
                    "default_count_mean_standard_error": _mean_standard_error(
                        arrays["default_count"]
                    ),
                    "loss_probability_standard_error": float(
                        np.sqrt(
                            np.mean(portfolio_result < 0.0)
                            * (1.0 - np.mean(portfolio_result < 0.0))
                            / iterations
                        )
                    ),
                },
            }
        )

    warnings: list[str] = []
    unscored_application_count = application_count - int(probabilities.size)
    if unscored_application_count:
        warnings.append(
            f"{unscored_application_count} applications were excluded because they lacked a usable score."
        )
    if len(model_versions) > 1:
        warnings.append(
            "Portfolio contains scores from multiple model versions; compare or re-score before policy use."
        )
    if operating_cost_per_approved == 0:
        warnings.append(
            "Operating cost is zero; set an evidence-based cost before interpreting financial results."
        )

    return {
        "application_count": application_count,
        "scored_application_count": int(probabilities.size),
        "unscored_application_count": unscored_application_count,
        "model_versions": model_versions,
        "portfolio_fingerprint": portfolio_fingerprint,
        "policy": {
            "name": policy.name,
            "description": policy.description,
            "approve_threshold": policy.approve_threshold,
            "decline_threshold": policy.decline_threshold,
            "auto_approve_count": int(auto_approved.sum()),
            "manual_review_count": int(reviewed.sum()),
            "auto_decline_count": int(auto_declined.sum()),
        },
        "assumptions": {
            "iterations": iterations,
            "seed": seed,
            "review_approval_rate": review_approval_rate,
            "interest_margin_rate": interest_margin_rate,
            "loss_given_default": loss_given_default,
            "operating_cost_per_approved": operating_cost_per_approved,
            "macro_volatility": macro_volatility,
            "calibration_volatility": calibration_volatility,
            "scenario_log_odds_shifts": {
                scenario: SCENARIO_LOG_ODDS_SHIFTS[scenario]
                for scenario in scenario_names
            },
            "borrower_iterations": simulation_cells,
        },
        "scenarios": scenario_results,
        "warnings": warnings,
        "note": SIMULATION_NOTE,
    }
