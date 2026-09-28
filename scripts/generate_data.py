"""
Synthetic data generator for the Enterprise Expense Integration Gateway.

Generates entirely fictional users, expense types, reports, items,
approvals, audit results, and integration logs — including deliberately
"messy" examples (duplicates, missing receipts, over-limit amounts,
failed integrations) so the audit/reporting/testing layers have
realistic data to exercise.

Usage:
    python scripts/generate_data.py --users 100 --reports 300 --items 1000 --seed 42

This script is intentionally decoupled from the API — it talks to
PostgreSQL directly via SQLAlchemy so it can run standalone in CI or
locally against docker-compose's postgres service.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.approval_audit import Approval, AuditResult, AuditRule  # noqa: E402
from app.models.enums import (  # noqa: E402
    ApprovalStatus,
    AuditResultStatus,
    ReportStatus,
    Severity,
    UserRole,
)
from app.models.expense import ExpenseItem, ExpenseReport, ExpenseType  # noqa: E402
from app.models.integration import IntegrationLog  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security.jwt import hash_password  # noqa: E402

DEPARTMENTS = [
    "Engineering", "Sales", "Marketing", "Finance", "Human Resources",
    "Customer Support", "Legal", "Operations", "IT", "Product",
]

EXPENSE_TYPES = [
    ("AIRFARE", "Airfare", "Travel", True),
    ("HOTEL", "Hotel", "Travel", True),
    ("MEALS", "Meals", "Travel", True),
    ("GROUND_TRANSPORT", "Ground Transportation", "Travel", False),
    ("OFFICE_SUPPLIES", "Office Supplies", "Office", False),
    ("SOFTWARE", "Software Subscription", "Office", True),
    ("CLIENT_ENTERTAINMENT", "Client Entertainment", "Client", True),
    ("TRAINING", "Training & Conferences", "Development", True),
    ("MOBILE", "Mobile Phone", "Office", False),
    ("PARKING", "Parking & Tolls", "Travel", False),
    ("SHIPPING", "Shipping & Postage", "Office", False),
    ("MISC", "Miscellaneous", "Other", False),
]

AUDIT_RULES = [
    dict(name="High-value Meals", rule_type="THRESHOLD", threshold=Decimal("150"),
         severity=Severity.WARNING, configuration={"category": "Travel"}),
    dict(name="Receipt Required", rule_type="RECEIPT_REQUIRED", threshold=None,
         severity=Severity.ERROR, configuration={}),
    dict(name="Duplicate Expense", rule_type="DUPLICATE", threshold=None,
         severity=Severity.ERROR, configuration={}),
    dict(name="Late Submission Policy", rule_type="POLICY_WINDOW", threshold=None,
         severity=Severity.WARNING, configuration={"max_days_after_transaction": 90}),
    dict(name="Personal Marked Billable", rule_type="PERSONAL_BILLABLE", threshold=None,
         severity=Severity.ERROR, configuration={}),
    dict(name="Unsupported Expense Type", rule_type="UNSUPPORTED_TYPE", threshold=None,
         severity=Severity.WARNING, configuration={}),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--reports", type=int, default=300)
    parser.add_argument("--items", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


async def generate(users_n: int, reports_n: int, items_n: int, seed: int) -> None:
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    async with AsyncSessionLocal() as session:
        # --- Expense types -------------------------------------------------
        expense_types = [
            ExpenseType(code=code, name=name, category=category, default_currency="USD", requires_receipt=req, active=True)
            for code, name, category, req in EXPENSE_TYPES
        ]
        session.add_all(expense_types)
        await session.flush()

        # --- Audit rules -----------------------------------------------------
        audit_rules = [AuditRule(**r, enabled=True) for r in AUDIT_RULES]
        session.add_all(audit_rules)
        await session.flush()

        # --- Users (managers first, so employees can reference them) --------
        managers = []
        for dept in DEPARTMENTS:
            m = User(
                employee_id=f"MGR{fake.unique.random_number(digits=5)}",
                name=fake.name(),
                email=fake.unique.company_email(),
                department=dept,
                role=UserRole.MANAGER,
                hashed_password=hash_password("Password123!"),
            )
            session.add(m)
            managers.append(m)
        await session.flush()

        admin = User(
            employee_id="ADMIN00001", name="System Administrator", email="admin@example-local.test",
            department="IT", role=UserRole.ADMIN, hashed_password=hash_password("Password123!"),
        )
        auditor = User(
            employee_id="AUD00001", name="Compliance Auditor", email="auditor@example-local.test",
            department="Finance", role=UserRole.AUDITOR, hashed_password=hash_password("Password123!"),
        )
        integration_svc = User(
            employee_id="SVC00001", name="Integration Service Account", email="integration-svc@example-local.test",
            department="IT", role=UserRole.INTEGRATION_SERVICE, hashed_password=hash_password("Password123!"),
        )
        session.add_all([admin, auditor, integration_svc])

        employees = []
        for _ in range(users_n):
            dept = random.choice(DEPARTMENTS)
            manager = next((m for m in managers if m.department == dept), random.choice(managers))
            u = User(
                employee_id=f"EMP{fake.unique.random_number(digits=5)}",
                name=fake.name(),
                email=fake.unique.email(),
                department=dept,
                manager_id=manager.id,
                role=UserRole.EMPLOYEE,
                hashed_password=hash_password("Password123!"),
            )
            session.add(u)
            employees.append(u)
        await session.flush()

        all_users = employees + managers

        # --- Expense reports + items ------------------------------------------
        reports = []
        for i in range(reports_n):
            user = random.choice(employees)
            status = random.choices(
                list(ReportStatus), weights=[10, 10, 5, 5, 15, 10, 20, 25], k=1
            )[0]
            report = ExpenseReport(
                report_number=f"ER-2026{random.randint(1,9):02d}-{100000+i}",
                user_id=user.id,
                title=f"{fake.bs().title()} expenses",
                currency="USD",
                status=status,
                total_amount=Decimal("0"),
            )
            session.add(report)
            reports.append((report, user))
        await session.flush()

        duplicate_seed_pool = []  # (report, vendor, amount, txn_date) reused deliberately
        items_created = 0
        while items_created < items_n:
            report, user = random.choice(reports)
            etype = random.choice(expense_types)

            force_duplicate = duplicate_seed_pool and random.random() < 0.03
            force_missing_receipt = random.random() < 0.08
            force_over_limit = random.random() < 0.05
            force_personal_billable = random.random() < 0.03

            if force_duplicate:
                vendor, amount, txn_date = random.choice(duplicate_seed_pool)
            else:
                vendor = fake.company()
                amount = Decimal(str(round(random.uniform(10, 200 if not force_over_limit else 5000), 2)))
                txn_date = fake.date_between(start_date="-180d", end_date="today")
                duplicate_seed_pool.append((vendor, amount, txn_date))
                if len(duplicate_seed_pool) > 50:
                    duplicate_seed_pool.pop(0)

            item = ExpenseItem(
                report_id=report.id,
                expense_type_id=etype.id,
                transaction_date=txn_date,
                vendor=vendor,
                amount=amount,
                currency="USD",
                description=fake.sentence(nb_words=6),
                receipt_reference=None if (force_missing_receipt and etype.requires_receipt) else f"RCPT-{fake.unique.random_number(digits=8)}",
                custom_fields={},
                billable=force_personal_billable or random.random() < 0.3,
                personal=force_personal_billable or random.random() < 0.1,
            )
            session.add(item)
            report.total_amount = (report.total_amount or Decimal("0")) + amount
            items_created += 1

        await session.flush()

        # --- Approvals for reports at/after PENDING_APPROVAL ------------------
        for report, user in reports:
            if report.status in (ReportStatus.PENDING_APPROVAL, ReportStatus.APPROVED, ReportStatus.PROCESSED, ReportStatus.REJECTED):
                manager = next((m for m in managers if m.id == user.manager_id), random.choice(managers))
                decided = report.status in (ReportStatus.APPROVED, ReportStatus.PROCESSED, ReportStatus.REJECTED)
                approval = Approval(
                    report_id=report.id,
                    approver_id=manager.id,
                    sequence=1,
                    status=(
                        ApprovalStatus.APPROVED if report.status in (ReportStatus.APPROVED, ReportStatus.PROCESSED)
                        else ApprovalStatus.REJECTED if report.status == ReportStatus.REJECTED
                        else ApprovalStatus.PENDING
                    ),
                    acted_at=datetime.now(timezone.utc) if decided else None,
                )
                session.add(approval)

        # --- A handful of explicit audit results for EXCEPTION reports --------
        receipt_rule = next(r for r in audit_rules if r.rule_type == "RECEIPT_REQUIRED")
        for report, user in reports:
            if report.status == ReportStatus.EXCEPTION:
                session.add(AuditResult(
                    report_id=report.id, expense_item_id=None, rule_id=receipt_rule.id,
                    result=AuditResultStatus.FAILED, severity=Severity.ERROR,
                    message="Receipt required but missing (synthetic exception example)",
                ))

        # --- Integration logs, including deliberate failures -------------------
        for i in range(150):
            success = random.random() < 0.85
            session.add(IntegrationLog(
                correlation_id=fake.uuid4(),
                request_id=fake.uuid4(),
                source_system="external_expense_system",
                target_system="expense_gateway",
                endpoint="/integrations/expenses",
                http_method="POST",
                status="SUCCEEDED" if success else "FAILED",
                retry_count=0 if success else random.randint(1, 3),
                duration_ms=random.randint(20, 900),
                error_code=None if success else random.choice(["UPSTREAM_TIMEOUT", "UPSTREAM_500", "RATE_LIMITED"]),
                error_message=None if success else "Synthetic failure example for reporting/demo purposes",
            ))

        await session.commit()

    print(f"Generated: {users_n} employees + {len(managers)} managers + 3 system users, "
          f"{len(expense_types)} expense types, {reports_n} reports, {items_created} items, "
          f"{len(audit_rules)} audit rules, 150 integration log entries.")


def main() -> None:
    args = parse_args()
    asyncio.run(generate(args.users, args.reports, args.items, args.seed))


if __name__ == "__main__":
    main()
