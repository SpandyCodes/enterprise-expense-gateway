from datetime import date
from decimal import Decimal

import pytest

from app.audit.audit_service import evaluate_report
from app.models.approval_audit import AuditRule
from app.models.enums import Severity
from app.models.expense import ExpenseItem, ExpenseReport, ExpenseType
from app.models.user import User
from app.security.jwt import hash_password

pytestmark = pytest.mark.integration


async def _make_user(db_session):
    user = User(
        employee_id="EMP-AUD-1", name="Audit Subject", email="audit-subject@example-local.test",
        department="Engineering", role="EMPLOYEE", hashed_password=hash_password("pw"),
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_duplicate_detection_flags_both_items(db_session):
    user = await _make_user(db_session)
    etype = ExpenseType(code="MEALS", name="Meals", category="Travel", requires_receipt=False)
    db_session.add(etype)
    await db_session.flush()

    rule = AuditRule(name="Duplicate Expense", rule_type="DUPLICATE", severity=Severity.ERROR, enabled=True, configuration={})
    db_session.add(rule)
    await db_session.flush()

    report = ExpenseReport(report_number="ER-TEST-0001", user_id=user.id, title="Trip", currency="USD", total_amount=Decimal("0"))
    db_session.add(report)
    await db_session.flush()

    common = dict(report_id=report.id, expense_type_id=etype.id, transaction_date=date(2026, 9, 1), vendor="Acme Diner", amount=Decimal("42.00"), currency="USD")
    db_session.add(ExpenseItem(**common))
    db_session.add(ExpenseItem(**common))
    await db_session.flush()

    results = await evaluate_report(db_session, report)
    assert len(results) == 2
    assert all("duplicate" in r.message.lower() for r in results)


async def test_receipt_required_rule_flags_missing_receipt(db_session):
    user = await _make_user(db_session)
    etype = ExpenseType(code="HOTEL", name="Hotel", category="Travel", requires_receipt=True)
    db_session.add(etype)
    await db_session.flush()

    rule = AuditRule(name="Receipt Required", rule_type="RECEIPT_REQUIRED", severity=Severity.ERROR, enabled=True, configuration={})
    db_session.add(rule)
    await db_session.flush()

    report = ExpenseReport(report_number="ER-TEST-0002", user_id=user.id, title="Trip", currency="USD", total_amount=Decimal("0"))
    db_session.add(report)
    await db_session.flush()

    db_session.add(ExpenseItem(
        report_id=report.id, expense_type_id=etype.id, transaction_date=date(2026, 9, 1),
        vendor="Hotel Co", amount=Decimal("300.00"), currency="USD", receipt_reference=None,
    ))
    await db_session.flush()

    results = await evaluate_report(db_session, report)
    assert len(results) == 1
    assert "receipt" in results[0].message.lower()
