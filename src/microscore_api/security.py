"""Authentication helpers for the MicroScore API prototype."""

from __future__ import annotations

from hashlib import pbkdf2_hmac
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, _digest = stored_hash.split("$", maxsplit=1)
    return secrets.compare_digest(hash_password(password, salt), stored_hash)


def create_token() -> str:
    return secrets.token_urlsafe(32)

