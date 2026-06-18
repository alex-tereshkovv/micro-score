"""Authentication helpers for the MicroScore API prototype."""

from __future__ import annotations

from hashlib import pbkdf2_hmac
import secrets


COMMON_PASSWORDS = {
    "1234567890",
    "admin123",
    "letmein123",
    "password",
    "password123",
    "qwerty123",
}


def password_policy_violations(password: str) -> list[str]:
    violations: list[str] = []
    if len(password) < 10:
        violations.append("use at least 10 characters")
    if not any(character.islower() for character in password):
        violations.append("include a lowercase letter")
    if not any(character.isupper() for character in password):
        violations.append("include an uppercase letter")
    if not any(character.isdigit() for character in password):
        violations.append("include a number")
    if password.isalnum():
        violations.append("include a symbol")
    if password.strip().lower() in COMMON_PASSWORDS:
        violations.append("avoid a common password")
    return violations


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, _digest = stored_hash.split("$", maxsplit=1)
    return secrets.compare_digest(hash_password(password, salt), stored_hash)


def create_token() -> str:
    return secrets.token_urlsafe(32)
