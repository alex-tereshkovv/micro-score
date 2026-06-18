"""Privacy checks applied at the borrower application boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any


FORBIDDEN_KEY_TOKENS = {
    "address",
    "biometric",
    "email",
    "iin",
    "latitude",
    "longitude",
    "passport",
    "phone",
    "photo",
    "voice",
}

FORBIDDEN_KEY_PHRASES = {
    "bank_statement",
    "device_fingerprint",
    "first_name",
    "full_name",
    "id_number",
    "last_name",
    "national_id",
    "phone_book",
    "precise_geolocation",
    "raw_transaction",
    "social_media",
    "transaction_description",
    "voice_recording",
}


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _key_is_forbidden(key: object) -> bool:
    normalized = _normalized_key(key)
    tokens = set(normalized.split("_"))
    return bool(tokens & FORBIDDEN_KEY_TOKENS) or any(
        phrase in normalized for phrase in FORBIDDEN_KEY_PHRASES
    )


def find_forbidden_signal_paths(
    value: Any,
    *,
    path: str = "behavioral_signals",
) -> list[str]:
    """Return sensitive field paths without attempting to inspect user values."""

    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if _key_is_forbidden(key):
                matches.append(child_path)
            matches.extend(find_forbidden_signal_paths(child, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            matches.extend(find_forbidden_signal_paths(child, path=f"{path}[{index}]"))
    return sorted(set(matches))
