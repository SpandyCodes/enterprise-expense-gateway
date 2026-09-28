import pytest

from tests.conftest import bearer_headers

pytestmark = pytest.mark.api


async def test_create_get_and_submit_report(client, sample_employee):
    headers = bearer_headers(sample_employee)

    create_resp = await client.post("/expense-reports", json={"title": "Client visit", "currency": "USD"}, headers=headers)
    assert create_resp.status_code == 201
    report = create_resp.json()
    assert report["status"] == "DRAFT"

    get_resp = await client.get(f"/expense-reports/{report['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == report["id"]

    submit_resp = await client.post(f"/expense-reports/{report['id']}/submit", headers=headers)
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "SUBMITTED"

    # Submitting again should be rejected (invalid transition)
    resubmit_resp = await client.post(f"/expense-reports/{report['id']}/submit", headers=headers)
    assert resubmit_resp.status_code == 400
    assert resubmit_resp.json()["error"]["code"] == "BAD_REQUEST"


async def test_add_item_to_report(client, sample_employee, db_session):
    from app.models.expense import ExpenseType

    etype = ExpenseType(code="MEALS", name="Meals", category="Travel", requires_receipt=False)
    db_session.add(etype)
    await db_session.commit()
    await db_session.refresh(etype)

    headers = bearer_headers(sample_employee)
    create_resp = await client.post("/expense-reports", json={"title": "Trip"}, headers=headers)
    report_id = create_resp.json()["id"]

    item_resp = await client.post(
        f"/expense-reports/{report_id}/items",
        json={
            "expense_type_id": str(etype.id),
            "transaction_date": "2026-09-01",
            "vendor": "Diner",
            "amount": "42.50",
            "currency": "USD",
        },
        headers=headers,
    )
    assert item_resp.status_code == 201
    assert item_resp.json()["vendor"] == "Diner"


async def test_get_nonexistent_report_returns_404(client, sample_employee):
    headers = bearer_headers(sample_employee)
    resp = await client.get("/expense-reports/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_get_report_without_token_is_unauthorized(client):
    resp = await client.get("/expense-reports/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401
