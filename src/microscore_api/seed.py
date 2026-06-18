"""Seed demo accounts and a demo application portfolio for local API testing."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .database import (
    DuplicateOrganizationError,
    DuplicateUserError,
    MicroScoreRepository,
)
from .scoring import get_scoring_service
from .security import hash_password

DEMO_PASSWORD = "password123"
DEMO_ORGANIZATION_ID = "pavlodar-demo-mfi"
DEMO_ORGANIZATION = {
    "organization_id": DEMO_ORGANIZATION_ID,
    "name": "Pavlodar Demo MFI",
    "region": "Pavlodar region, Kazakhstan",
}

DEMO_USERS: tuple[dict[str, str], ...] = (
    {"email": "borrower@test.com", "role": "borrower"},
    {"email": "analyst@test.com", "role": "mfi_analyst"},
    {"email": "admin@test.com", "role": "admin"},
)

DEMO_APPLICATION_ID = "demo-application-pavlodar-001"


def _application(
    index: int,
    *,
    borrower_email: str,
    requested_amount: float,
    purpose: str,
    district: str,
    settlement_type: str,
    annual_income: float,
    total_outstanding_debt: float,
    mobile_banking_logins: int,
    online_transfer_frequency: int,
    atm_withdrawal_frequency: int,
    avg_deposit_amount: float,
    debit_card_spending: float,
    num_open_loans: int,
    late_payment_count: int,
    gender: str,
    employment_status: str,
) -> dict[str, Any]:
    return {
        "application_id": f"demo-application-pavlodar-{index:03d}",
        "borrower_email": borrower_email,
        "requested_amount": requested_amount,
        "purpose": purpose,
        "district": district,
        "settlement_type": settlement_type,
        "behavioral_signals": {
            "annual_income": annual_income,
            "total_outstanding_debt": total_outstanding_debt,
            "mobile_banking_logins": mobile_banking_logins,
            "online_transfer_frequency": online_transfer_frequency,
            "atm_withdrawal_frequency": atm_withdrawal_frequency,
            "avg_deposit_amount": avg_deposit_amount,
            "debit_card_spending": debit_card_spending,
            "loan_application_amount": requested_amount / 100,
            "num_open_loans": num_open_loans,
            "late_payment_count": late_payment_count,
            "gender": gender,
            "employment_status": employment_status,
            "settlement_type": settlement_type,
            "pavlodar_district": district,
        },
    }


DEMO_APPLICATIONS: tuple[dict[str, Any], ...] = (
    _application(
        1,
        borrower_email="borrower@test.com",
        requested_amount=300_000,
        purpose="working capital",
        district="Pavlodar city",
        settlement_type="urban",
        annual_income=52_000,
        total_outstanding_debt=6_500,
        mobile_banking_logins=18,
        online_transfer_frequency=7,
        atm_withdrawal_frequency=2,
        avg_deposit_amount=1_400,
        debit_card_spending=900,
        num_open_loans=1,
        late_payment_count=0,
        gender="Female",
        employment_status="Self-employed",
    ),
    _application(
        2,
        borrower_email="borrower.ekibastuz.001@test.com",
        requested_amount=450_000,
        purpose="equipment repair",
        district="Ekibastuz",
        settlement_type="industrial_city",
        annual_income=49_000,
        total_outstanding_debt=15_000,
        mobile_banking_logins=8,
        online_transfer_frequency=2,
        atm_withdrawal_frequency=5,
        avg_deposit_amount=900,
        debit_card_spending=1_200,
        num_open_loans=2,
        late_payment_count=2,
        gender="Male",
        employment_status="Employed",
    ),
    _application(
        3,
        borrower_email="borrower.bayanaul.001@test.com",
        requested_amount=250_000,
        purpose="seasonal livestock income",
        district="Bayanaul",
        settlement_type="rural",
        annual_income=43_000,
        total_outstanding_debt=9_000,
        mobile_banking_logins=5,
        online_transfer_frequency=1,
        atm_withdrawal_frequency=6,
        avg_deposit_amount=700,
        debit_card_spending=850,
        num_open_loans=1,
        late_payment_count=1,
        gender="Female",
        employment_status="Self-employed",
    ),
    _application(
        4,
        borrower_email="borrower.aksu.001@test.com",
        requested_amount=500_000,
        purpose="home renovation",
        district="Aksu",
        settlement_type="industrial_city",
        annual_income=65_000,
        total_outstanding_debt=5_000,
        mobile_banking_logins=25,
        online_transfer_frequency=9,
        atm_withdrawal_frequency=2,
        avg_deposit_amount=1_900,
        debit_card_spending=1_050,
        num_open_loans=1,
        late_payment_count=0,
        gender="Male",
        employment_status="Employed",
    ),
    _application(
        5,
        borrower_email="borrower.irtysh.001@test.com",
        requested_amount=180_000,
        purpose="urgent household expense",
        district="Irtysh",
        settlement_type="rural",
        annual_income=28_000,
        total_outstanding_debt=18_000,
        mobile_banking_logins=2,
        online_transfer_frequency=0,
        atm_withdrawal_frequency=8,
        avg_deposit_amount=350,
        debit_card_spending=950,
        num_open_loans=3,
        late_payment_count=4,
        gender="Other",
        employment_status="Unemployed",
    ),
    _application(
        6,
        borrower_email="borrower.uspenka.001@test.com",
        requested_amount=150_000,
        purpose="farm inputs",
        district="Uspenka",
        settlement_type="rural",
        annual_income=36_000,
        total_outstanding_debt=12_000,
        mobile_banking_logins=4,
        online_transfer_frequency=1,
        atm_withdrawal_frequency=7,
        avg_deposit_amount=520,
        debit_card_spending=780,
        num_open_loans=2,
        late_payment_count=3,
        gender="Female",
        employment_status="Self-employed",
    ),
    _application(
        7,
        borrower_email="borrower.pavlodar-district.001@test.com",
        requested_amount=350_000,
        purpose="vehicle repair",
        district="Pavlodar district",
        settlement_type="peri_urban",
        annual_income=58_000,
        total_outstanding_debt=3_000,
        mobile_banking_logins=22,
        online_transfer_frequency=8,
        atm_withdrawal_frequency=1,
        avg_deposit_amount=1_600,
        debit_card_spending=780,
        num_open_loans=0,
        late_payment_count=0,
        gender="Male",
        employment_status="Employed",
    ),
    _application(
        8,
        borrower_email="borrower.zhelezinka.001@test.com",
        requested_amount=220_000,
        purpose="market stall inventory",
        district="Zhelezinka",
        settlement_type="rural",
        annual_income=41_000,
        total_outstanding_debt=10_000,
        mobile_banking_logins=6,
        online_transfer_frequency=2,
        atm_withdrawal_frequency=6,
        avg_deposit_amount=650,
        debit_card_spending=820,
        num_open_loans=2,
        late_payment_count=2,
        gender="Female",
        employment_status="Employed",
    ),
    _application(
        9,
        borrower_email="borrower.sharbakty.001@test.com",
        requested_amount=300_000,
        purpose="small shop inventory",
        district="Sharbakty",
        settlement_type="rural",
        annual_income=48_000,
        total_outstanding_debt=7_000,
        mobile_banking_logins=10,
        online_transfer_frequency=3,
        atm_withdrawal_frequency=4,
        avg_deposit_amount=1_000,
        debit_card_spending=850,
        num_open_loans=1,
        late_payment_count=1,
        gender="Male",
        employment_status="Self-employed",
    ),
    _application(
        10,
        borrower_email="borrower.terenkol.001@test.com",
        requested_amount=200_000,
        purpose="education expense",
        district="Terenkol",
        settlement_type="rural",
        annual_income=53_000,
        total_outstanding_debt=4_000,
        mobile_banking_logins=12,
        online_transfer_frequency=4,
        atm_withdrawal_frequency=3,
        avg_deposit_amount=1_100,
        debit_card_spending=760,
        num_open_loans=1,
        late_payment_count=0,
        gender="Female",
        employment_status="Employed",
    ),
    _application(
        11,
        borrower_email="borrower.aktogay.001@test.com",
        requested_amount=120_000,
        purpose="medical expense",
        district="Aktogay",
        settlement_type="rural",
        annual_income=25_000,
        total_outstanding_debt=22_000,
        mobile_banking_logins=1,
        online_transfer_frequency=0,
        atm_withdrawal_frequency=9,
        avg_deposit_amount=250,
        debit_card_spending=1_050,
        num_open_loans=4,
        late_payment_count=5,
        gender="Male",
        employment_status="Unemployed",
    ),
    _application(
        12,
        borrower_email="borrower.akkuly.001@test.com",
        requested_amount=160_000,
        purpose="agricultural equipment",
        district="Akkuly",
        settlement_type="rural",
        annual_income=39_000,
        total_outstanding_debt=16_000,
        mobile_banking_logins=3,
        online_transfer_frequency=1,
        atm_withdrawal_frequency=8,
        avg_deposit_amount=460,
        debit_card_spending=880,
        num_open_loans=3,
        late_payment_count=2,
        gender="Female",
        employment_status="Self-employed",
    ),
    _application(
        13,
        borrower_email="borrower.may.001@test.com",
        requested_amount=180_000,
        purpose="family business cash gap",
        district="May district",
        settlement_type="rural",
        annual_income=37_000,
        total_outstanding_debt=8_000,
        mobile_banking_logins=7,
        online_transfer_frequency=1,
        atm_withdrawal_frequency=6,
        avg_deposit_amount=620,
        debit_card_spending=700,
        num_open_loans=1,
        late_payment_count=1,
        gender="Other",
        employment_status="Employed",
    ),
    _application(
        14,
        borrower_email="borrower.pavlodar.002@test.com",
        requested_amount=600_000,
        purpose="business expansion",
        district="Pavlodar city",
        settlement_type="urban",
        annual_income=72_000,
        total_outstanding_debt=0,
        mobile_banking_logins=35,
        online_transfer_frequency=15,
        atm_withdrawal_frequency=1,
        avg_deposit_amount=2_600,
        debit_card_spending=1_300,
        num_open_loans=0,
        late_payment_count=0,
        gender="Male",
        employment_status="Employed",
    ),
    _application(
        15,
        borrower_email="borrower.ekibastuz.002@test.com",
        requested_amount=420_000,
        purpose="winter heating stock",
        district="Ekibastuz",
        settlement_type="industrial_city",
        annual_income=46_000,
        total_outstanding_debt=20_000,
        mobile_banking_logins=9,
        online_transfer_frequency=2,
        atm_withdrawal_frequency=7,
        avg_deposit_amount=720,
        debit_card_spending=1_100,
        num_open_loans=3,
        late_payment_count=3,
        gender="Female",
        employment_status="Self-employed",
    ),
    _application(
        16,
        borrower_email="borrower.pavlodar.003@test.com",
        requested_amount=100_000,
        purpose="short-term bridge loan",
        district="Pavlodar city",
        settlement_type="urban",
        annual_income=31_000,
        total_outstanding_debt=11_000,
        mobile_banking_logins=15,
        online_transfer_frequency=5,
        atm_withdrawal_frequency=3,
        avg_deposit_amount=800,
        debit_card_spending=850,
        num_open_loans=2,
        late_payment_count=1,
        gender="Female",
        employment_status="Unemployed",
    ),
    _application(
        17,
        borrower_email="borrower.irtysh.002@test.com",
        requested_amount=260_000,
        purpose="debt consolidation",
        district="Irtysh",
        settlement_type="rural",
        annual_income=30_000,
        total_outstanding_debt=24_000,
        mobile_banking_logins=2,
        online_transfer_frequency=0,
        atm_withdrawal_frequency=10,
        avg_deposit_amount=280,
        debit_card_spending=1_150,
        num_open_loans=4,
        late_payment_count=5,
        gender="Female",
        employment_status="Unemployed",
    ),
    _application(
        18,
        borrower_email="borrower.aksu.002@test.com",
        requested_amount=380_000,
        purpose="tool purchase",
        district="Aksu",
        settlement_type="industrial_city",
        annual_income=44_000,
        total_outstanding_debt=18_000,
        mobile_banking_logins=7,
        online_transfer_frequency=2,
        atm_withdrawal_frequency=6,
        avg_deposit_amount=680,
        debit_card_spending=1_050,
        num_open_loans=3,
        late_payment_count=3,
        gender="Male",
        employment_status="Self-employed",
    ),
    _application(
        19,
        borrower_email="borrower.zhelezinka.002@test.com",
        requested_amount=210_000,
        purpose="crop-season bridge",
        district="Zhelezinka",
        settlement_type="rural",
        annual_income=34_000,
        total_outstanding_debt=15_000,
        mobile_banking_logins=4,
        online_transfer_frequency=1,
        atm_withdrawal_frequency=8,
        avg_deposit_amount=430,
        debit_card_spending=920,
        num_open_loans=3,
        late_payment_count=4,
        gender="Male",
        employment_status="Self-employed",
    ),
    _application(
        20,
        borrower_email="borrower.pavlodar-district.002@test.com",
        requested_amount=290_000,
        purpose="delivery vehicle maintenance",
        district="Pavlodar district",
        settlement_type="peri_urban",
        annual_income=42_000,
        total_outstanding_debt=13_000,
        mobile_banking_logins=11,
        online_transfer_frequency=3,
        atm_withdrawal_frequency=4,
        avg_deposit_amount=760,
        debit_card_spending=980,
        num_open_loans=2,
        late_payment_count=2,
        gender="Other",
        employment_status="Employed",
    ),
)

DEMO_APPLICATION = DEMO_APPLICATIONS[0]
DEMO_PORTFOLIO_BORROWERS: tuple[dict[str, str], ...] = tuple(
    {
        "email": application["borrower_email"],
        "role": "borrower",
    }
    for application in DEMO_APPLICATIONS
    if application["borrower_email"] != "borrower@test.com"
)


def _seed_user(
    repository: MicroScoreRepository,
    *,
    email: str,
    role: str,
    organization_id: str | None = None,
) -> bool:
    try:
        repository.create_user(
            email,
            hash_password(DEMO_PASSWORD),
            role,
            organization_id,
        )
    except DuplicateUserError:
        if organization_id:
            repository.assign_user_organization(email, organization_id)
        return False
    return True


def seed_demo_data(
    repository: MicroScoreRepository | None = None,
    *,
    score_applications: bool = True,
) -> dict[str, Any]:
    repository = repository or MicroScoreRepository()
    created_users: list[str] = []
    existing_users: list[str] = []
    created_portfolio_borrowers: list[str] = []
    existing_portfolio_borrowers: list[str] = []
    created_applications: list[str] = []
    existing_applications: list[str] = []
    scored_applications: list[str] = []

    try:
        repository.create_organization(**DEMO_ORGANIZATION)
    except DuplicateOrganizationError:
        pass

    for user in DEMO_USERS:
        created = _seed_user(
            repository,
            email=user["email"],
            role=user["role"],
            organization_id=(
                DEMO_ORGANIZATION_ID if user["role"] == "mfi_analyst" else None
            ),
        )
        if created:
            created_users.append(user["email"])
        else:
            existing_users.append(user["email"])

    for user in DEMO_PORTFOLIO_BORROWERS:
        created = _seed_user(
            repository,
            email=user["email"],
            role=user["role"],
        )
        if created:
            created_portfolio_borrowers.append(user["email"])
        else:
            existing_portfolio_borrowers.append(user["email"])

    scoring_service = None

    for application in DEMO_APPLICATIONS:
        application_id = application["application_id"]
        existing = repository.get_application(application_id)
        if existing is None:
            current = repository.create_application(
                **application,
                organization_id=DEMO_ORGANIZATION_ID,
            )
            created_applications.append(application_id)
        else:
            repository.assign_application_organization(
                application_id,
                DEMO_ORGANIZATION_ID,
            )
            current = repository.get_application(application_id) or existing
            existing_applications.append(application_id)

        if score_applications and current.get("score_result") is None:
            if scoring_service is None:
                scoring_service = get_scoring_service()
            score_result = asdict(scoring_service.score(current["behavioral_signals"]))
            repository.update_application_score(
                application_id=application_id,
                score_result=score_result,
                actor_email="analyst@test.com",
            )
            scored_applications.append(application_id)

    application_status = (
        "created"
        if DEMO_APPLICATION_ID in created_applications
        else "already_exists"
    )

    return {
        "database": str(repository.db_path),
        "demo_organization_id": DEMO_ORGANIZATION_ID,
        "demo_password": DEMO_PASSWORD,
        "created_users": created_users,
        "existing_users": existing_users,
        "created_portfolio_borrowers": created_portfolio_borrowers,
        "existing_portfolio_borrowers": existing_portfolio_borrowers,
        "demo_application_id": DEMO_APPLICATION_ID,
        "demo_application_status": application_status,
        "demo_application_ids": [application["application_id"] for application in DEMO_APPLICATIONS],
        "created_applications": created_applications,
        "existing_applications": existing_applications,
        "scored_applications": scored_applications,
        "demo_portfolio_size": len(DEMO_APPLICATIONS),
    }


def main() -> int:
    result = seed_demo_data()
    print("MicroScore demo data")
    print(f"Database: {result['database']}")
    print(f"Password for demo accounts: {result['demo_password']}")
    print(f"Created users: {', '.join(result['created_users']) or 'none'}")
    print(f"Existing users: {', '.join(result['existing_users']) or 'none'}")
    print(
        "Portfolio borrowers: "
        f"{len(result['created_portfolio_borrowers'])} created, "
        f"{len(result['existing_portfolio_borrowers'])} existing"
    )
    print(f"Primary demo application: {result['demo_application_id']} ({result['demo_application_status']})")
    print(
        "Demo portfolio: "
        f"{result['demo_portfolio_size']} applications, "
        f"{len(result['created_applications'])} created, "
        f"{len(result['existing_applications'])} existing, "
        f"{len(result['scored_applications'])} newly scored"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
