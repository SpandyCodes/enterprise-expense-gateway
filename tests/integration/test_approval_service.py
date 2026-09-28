from decimal import Decimal

import pytest

from app.services.approval_service import create_approval_chain, resolve_chain_for_amount
from app.models.expense import ExpenseReport
from app.models.user import User
from app.security.jwt import hash_password

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "amount,expected_levels",
    [
        (Decimal("100"), ("MANAGER",)),
        (Decimal("4999.99"), ("MANAGER",)),
        (Decimal("5000"), ("MANAGER", "FINANCE")),
        (Decimal("24999.99"), ("MANAGER", "FINANCE")),
        (Decimal("25000"), ("MANAGER", "FINANCE", "SENIOR")),
        (Decimal("100000"), ("MANAGER", "FINANCE", "SENIOR")),
    ],
)
def test_resolve_chain_for_amount(amount, expected_levels):
    assert resolve_chain_for_amount(amount) == expected_levels


async def test_create_approval_chain_persists_one_row_per_level(db_session):
    manager = User(employee_id="MGR-1", name="Mgr", email="mgr@example-local.test", department="Eng", role="MANAGER", hashed_password=hash_password("pw"))
    db_session.add(manager)
    await db_session.flush()

    employee = User(employee_id="EMP-1", name="Emp", email="emp@example-local.test", department="Eng", role="EMPLOYEE", manager_id=manager.id, hashed_password=hash_password("pw"))
    db_session.add(employee)
    await db_session.flush()

    report = ExpenseReport(report_number="ER-TEST-APP-1", user_id=employee.id, title="Big trip", currency="USD", total_amount=Decimal("6000"))
    db_session.add(report)
    await db_session.flush()

    approvals = await create_approval_chain(db_session, report, employee)
    await db_session.flush()

    assert len(approvals) == 2  # MANAGER + FINANCE tier
    assert approvals[0].approver_id == manager.id
    assert [a.sequence for a in approvals] == [1, 2]
