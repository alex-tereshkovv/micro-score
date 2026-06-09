"""Seed demo accounts and a demo application for local API testing."""

from __future__ import annotations

from typing import Any

from .database import DuplicateUserError, MicroScoreRepository
from .security import hash_password

DEMO_PASSWORD = "password123"

DEMO_USERS: tuple[dict[str, str], ...] = (
    {"email": "borrower@test.com", "role": "borrower"},
    {"email": "analyst@test.com", "role": "mfi_analyst"},
    {"email": "admin@test.com", "role": "admin"},
)

DEMO_APPLICATION_ID = "demo-application-pavlodar-001"

DEMO_APPLICATION: dict[str, Any] = {
    "application_id": DEMO_APPLICATION_ID,
    "borrower_email": "borrower@test.com",
    "requested_amount": 300_000,
    "purpose": "working capital",
    "district": "Pavlodar city",
    "settlement_type": "urban",
    "behavioral_signals": {
        "annual_income": 52_000,
        "total_outstanding_debt": 6_500,
        "mobile_banking_logins": 18,
        "online_transfer_frequency": 7,
        "atm_withdrawal_frequency": 2,
        "avg_deposit_amount": 1_400,
        "debit_card_spending": 900,
        "loan_application_amount": 3_000,
        "num_open_loans": 1,
        "late_payment_count": 0,
        "gender": "Female",
        "employment_status": "Self-employed",
        "settlement_type": "urban",
        "pavlodar_district": "Pavlodar city",
    },
}


def seed_demo_data(repository: MicroScoreRepository | None = None) -> dict[str, Any]:
    repository = repository or MicroScoreRepository()
    created_users: list[str] = []
    existing_users: list[str] = []

    for user in DEMO_USERS:
        try:
            repository.create_user(
                user["email"],
                hash_password(DEMO_PASSWORD),
                user["role"],
            )
            created_users.append(user["email"])
        except DuplicateUserError:
            existing_users.append(user["email"])

    if repository.get_application(DEMO_APPLICATION_ID) is None:
        repository.create_application(**DEMO_APPLICATION)
        application_status = "created"
    else:
        application_status = "already_exists"

    return {
        "database": str(repository.db_path),
        "demo_password": DEMO_PASSWORD,
        "created_users": created_users,
        "existing_users": existing_users,
        "demo_application_id": DEMO_APPLICATION_ID,
        "demo_application_status": application_status,
    }


def main() -> int:
    result = seed_demo_data()
    print("MicroScore demo data")
    print(f"Database: {result['database']}")
    print(f"Password for demo accounts: {result['demo_password']}")
    print(f"Created users: {', '.join(result['created_users']) or 'none'}")
    print(f"Existing users: {', '.join(result['existing_users']) or 'none'}")
    print(f"Demo application: {result['demo_application_id']} ({result['demo_application_status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
