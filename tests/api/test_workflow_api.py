import pytest

from app.models.approval_audit import AuditRule
from app.models.enums import Severity
from app.models.expense import ExpenseType
from tests.conftest import bearer_headers
from tests.helpers import make_user

pytestmark = pytest.mark.api


async def _setup(db, requires_receipt=False):
    manager = await make_user(db, "MANAGER")
    employee = await make_user(db, "EMPLOYEE", manager_id=manager.id)
    auditor = await make_user(db, "AUDITOR")
    admin = await make_user(db, "ADMIN")
    etype = ExpenseType(code="MEALS", name="Meals", category="Travel", requires_receipt=requires_receipt)
    db.add(etype)
    await db.commit()
    await db.refresh(etype)
    return manager, employee, auditor, admin, etype


async def _submitted_report(client, employee, etype, receipt="rcpt-1"):
    headers = bearer_headers(employee)
    created = await client.post("/expense-reports", json={"title": "Trip"}, headers=headers)
    report_id = created.json()["id"]
    item = {
        "expense_type_id": str(etype.id),
        "transaction_date": "2026-09-01",
        "vendor": "Diner",
        "amount": "100.00",
        "currency": "USD",
        "receipt_reference": receipt,
    }
    assert (await client.post(f"/expense-reports/{report_id}/items", json=item, headers=headers)).status_code == 201
    assert (await client.post(f"/expense-reports/{report_id}/submit", headers=headers)).status_code == 200
    return report_id


async def test_full_happy_path_to_processed(client, db_session):
    manager, employee, auditor, admin, etype = await _setup(db_session)
    rid = await _submitted_report(client, employee, etype)

    audited = await client.post(f"/expense-reports/{rid}/audit", headers=bearer_headers(auditor))
    assert audited.status_code == 200
    assert audited.json()["status"] == "PENDING_APPROVAL"

    approved = await client.post(f"/expense-reports/{rid}/approve", headers=bearer_headers(manager))
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    processed = await client.post(f"/expense-reports/{rid}/process", headers=bearer_headers(admin))
    assert processed.status_code == 200
    assert processed.json()["status"] == "PROCESSED"


async def test_reject_path(client, db_session):
    manager, employee, auditor, _, etype = await _setup(db_session)
    rid = await _submitted_report(client, employee, etype)
    await client.post(f"/expense-reports/{rid}/audit", headers=bearer_headers(auditor))

    rejected = await client.post(f"/expense-reports/{rid}/reject", headers=bearer_headers(manager))
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"

    # the pending approval was consumed, so a second decision is refused
    again = await client.post(f"/expense-reports/{rid}/approve", headers=bearer_headers(manager))
    assert again.status_code == 400


async def test_audit_error_moves_report_to_exception(client, db_session):
    manager, employee, auditor, _, etype = await _setup(db_session, requires_receipt=True)
    db_session.add(AuditRule(name="Receipt Required", rule_type="RECEIPT_REQUIRED",
                             severity=Severity.ERROR, enabled=True, configuration={}))
    await db_session.commit()
    rid = await _submitted_report(client, employee, etype, receipt=None)

    audited = await client.post(f"/expense-reports/{rid}/audit", headers=bearer_headers(auditor))
    assert audited.status_code == 200
    assert audited.json()["status"] == "EXCEPTION"

    results = await client.get(f"/expense-reports/{rid}/audit-results", headers=bearer_headers(auditor))
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert "receipt" in results.json()[0]["message"].lower()


async def test_process_before_approval_is_rejected(client, db_session):
    _, employee, auditor, admin, etype = await _setup(db_session)
    rid = await _submitted_report(client, employee, etype)
    await client.post(f"/expense-reports/{rid}/audit", headers=bearer_headers(auditor))

    resp = await client.post(f"/expense-reports/{rid}/process", headers=bearer_headers(admin))
    assert resp.status_code == 400


async def test_employee_cannot_approve(client, db_session):
    _, employee, auditor, _, etype = await _setup(db_session)
    rid = await _submitted_report(client, employee, etype)
    await client.post(f"/expense-reports/{rid}/audit", headers=bearer_headers(auditor))

    resp = await client.post(f"/expense-reports/{rid}/approve", headers=bearer_headers(employee))
    assert resp.status_code == 403


async def test_unrelated_manager_cannot_approve(client, db_session):
    _, employee, auditor, _, etype = await _setup(db_session)
    other_manager = await make_user(db_session, "MANAGER")
    rid = await _submitted_report(client, employee, etype)
    await client.post(f"/expense-reports/{rid}/audit", headers=bearer_headers(auditor))

    resp = await client.post(f"/expense-reports/{rid}/approve", headers=bearer_headers(other_manager))
    assert resp.status_code == 400


async def test_list_reports_and_items(client, db_session):
    manager, employee, _, _, etype = await _setup(db_session)
    rid = await _submitted_report(client, employee, etype)

    reports = await client.get("/expense-reports", headers=bearer_headers(manager))
    assert reports.status_code == 200
    assert any(r["id"] == rid for r in reports.json())

    items = await client.get(f"/expense-reports/{rid}/items", headers=bearer_headers(employee))
    assert items.status_code == 200
    assert len(items.json()) == 1