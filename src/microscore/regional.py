"""Pavlodar-region simulation utilities.

The current public dataset has no local geography. This module adds a
transparent, deterministic regional layer for research design and demos without
pretending that the simulated fields are observed real-world MFI data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DistrictProfile:
    district: str
    settlement_type: str
    base_weight: float
    distance_to_pavlodar_km: float
    digital_access_index: float
    income_index: float
    mfi_branch_access_index: float
    seasonal_income_risk: float


PAVLODAR_DISTRICT_PROFILES: tuple[DistrictProfile, ...] = (
    DistrictProfile("Pavlodar city", "urban", 0.24, 0, 0.92, 1.12, 0.95, 0.18),
    DistrictProfile("Ekibastuz", "industrial_city", 0.18, 135, 0.82, 1.06, 0.82, 0.28),
    DistrictProfile("Aksu", "industrial_city", 0.10, 50, 0.78, 1.02, 0.74, 0.30),
    DistrictProfile("Pavlodar district", "peri_urban", 0.08, 35, 0.68, 0.96, 0.62, 0.42),
    DistrictProfile("Bayanaul", "rural", 0.07, 220, 0.54, 0.88, 0.45, 0.68),
    DistrictProfile("Aktogay", "rural", 0.06, 125, 0.50, 0.84, 0.40, 0.64),
    DistrictProfile("Uspenka", "rural", 0.06, 95, 0.48, 0.82, 0.38, 0.66),
    DistrictProfile("Sharbakty", "rural", 0.06, 90, 0.50, 0.84, 0.40, 0.62),
    DistrictProfile("Zhelezinka", "rural", 0.05, 180, 0.44, 0.80, 0.34, 0.70),
    DistrictProfile("Terenkol", "rural", 0.04, 110, 0.46, 0.81, 0.36, 0.67),
    DistrictProfile("Irtysh", "rural", 0.03, 160, 0.42, 0.78, 0.32, 0.72),
    DistrictProfile("May district", "rural", 0.03, 210, 0.38, 0.76, 0.28, 0.76),
)


def district_profile_table() -> pd.DataFrame:
    """Return the simulation assumptions in a readable table."""

    return pd.DataFrame([profile.__dict__ for profile in PAVLODAR_DISTRICT_PROFILES])


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.mean()) / std


def _row_profile_probabilities(frame: pd.DataFrame) -> np.ndarray:
    profiles = district_profile_table()
    base = profiles["base_weight"].to_numpy(dtype=float)
    base = base / base.sum()

    income_z = _zscore(frame.get("annual_income", pd.Series(0, index=frame.index))).to_numpy()
    balance_z = _zscore(frame.get("avg_monthly_balance", pd.Series(0, index=frame.index))).to_numpy()
    digital_activity = (
        frame.get("mobile_banking_logins", pd.Series(0, index=frame.index))
        + frame.get("online_transfer_frequency", pd.Series(0, index=frame.index))
        - frame.get("atm_withdrawal_frequency", pd.Series(0, index=frame.index))
    )
    digital_z = _zscore(digital_activity).to_numpy()

    income_index = profiles["income_index"].to_numpy(dtype=float)
    digital_index = profiles["digital_access_index"].to_numpy(dtype=float)
    seasonality = profiles["seasonal_income_risk"].to_numpy(dtype=float)

    income_component = np.outer(income_z, income_index - income_index.mean())
    balance_component = np.outer(balance_z, income_index - income_index.mean())
    digital_component = np.outer(digital_z, digital_index - digital_index.mean())
    seasonal_component = np.outer(-income_z, seasonality - seasonality.mean())

    logits = (
        np.log(base)
        + 0.45 * income_component
        + 0.25 * balance_component
        + 0.55 * digital_component
        + 0.35 * seasonal_component
    )
    logits = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities = probabilities / probabilities.sum(axis=1, keepdims=True)
    return probabilities


def add_pavlodar_regional_context(
    frame: pd.DataFrame,
    *,
    random_state: int = 42,
) -> pd.DataFrame:
    """Add reproducible Pavlodar-region context fields to a borrower dataset."""

    result = frame.copy()
    profiles = district_profile_table()
    probabilities = _row_profile_probabilities(result)
    rng = np.random.default_rng(random_state)

    profile_indices = np.array(
        [
            rng.choice(len(profiles), p=row_probabilities)
            for row_probabilities in probabilities
        ]
    )
    assigned = profiles.iloc[profile_indices].reset_index(drop=True)

    result["pavlodar_district"] = assigned["district"].to_numpy()
    result["settlement_type"] = assigned["settlement_type"].to_numpy()
    result["distance_to_pavlodar_km"] = assigned["distance_to_pavlodar_km"].to_numpy()
    result["regional_digital_access_index"] = assigned["digital_access_index"].to_numpy()
    result["regional_income_index"] = assigned["income_index"].to_numpy()
    result["mfi_branch_access_index"] = assigned["mfi_branch_access_index"].to_numpy()
    result["seasonal_income_risk"] = assigned["seasonal_income_risk"].to_numpy()
    result["financial_access_gap"] = (
        1.0
        - (
            0.55 * result["regional_digital_access_index"]
            + 0.45 * result["mfi_branch_access_index"]
        )
    ).clip(lower=0.0, upper=1.0)
    result["rural_flag"] = (result["settlement_type"] == "rural").astype(int)

    return result


def regional_summary(
    frame: pd.DataFrame,
    *,
    target: str = "credit_risk",
) -> pd.DataFrame:
    """Summarize borrower and risk patterns by simulated district."""

    required = {"pavlodar_district", "settlement_type"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Regional columns are missing: {missing}")

    aggregations: dict[str, tuple[str, str]] = {
        "n": (target, "size"),
        "high_risk_rate": (target, "mean"),
    }
    optional_columns = {
        "avg_income": ("annual_income", "mean"),
        "avg_loan_amount": ("loan_application_amount", "mean"),
        "avg_mobile_logins": ("mobile_banking_logins", "mean"),
        "avg_financial_access_gap": ("financial_access_gap", "mean"),
        "avg_distance_to_pavlodar_km": ("distance_to_pavlodar_km", "mean"),
        "avg_seasonal_income_risk": ("seasonal_income_risk", "mean"),
    }
    for output_column, (source_column, statistic) in optional_columns.items():
        if source_column in frame.columns:
            aggregations[output_column] = (source_column, statistic)

    return (
        frame.groupby(["pavlodar_district", "settlement_type"], dropna=False)
        .agg(**aggregations)
        .reset_index()
        .sort_values(["settlement_type", "pavlodar_district"])
    )
