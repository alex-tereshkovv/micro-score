"""Project paths used by notebooks and command-line entrypoints."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "credit_risk_dataset.csv"
LEGACY_NOTEBOOK_DATA_PATH = PROJECT_ROOT / "notebooks" / "data" / "credit_risk_dataset.csv"


def resolve_data_path(path: str | Path | None = None) -> Path:
    """Resolve the dataset path and provide a clear migration fallback."""

    candidate = DEFAULT_DATA_PATH if path is None else Path(path)
    if candidate.exists():
        return candidate

    if candidate == LEGACY_NOTEBOOK_DATA_PATH and DEFAULT_DATA_PATH.exists():
        return DEFAULT_DATA_PATH

    raise FileNotFoundError(
        "Could not find the MicroScore dataset. Expected it at "
        f"'{DEFAULT_DATA_PATH}'. The old notebook path "
        f"'{LEGACY_NOTEBOOK_DATA_PATH}' was removed when data moved to data/raw."
    )
