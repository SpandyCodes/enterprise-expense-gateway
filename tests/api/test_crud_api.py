import pytest

from tests.conftest import bearer_headers
from tests.helpers import make_user

pytestmark = pytest.mark.api


async def test_health_and_ready(client):
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200


async def test_admin_manages_expense_types(client, db_session):
    admin = await make_user(db_session, "ADMIN")
    headers = bearer_headers(admin)
    created = await client.post("/expense-types", json={"code": "TAXI", "name": "Taxi", "category": "Travel"}, headers=headers)
    assert created.status_code == 201
    listed = await client.get("/expense-types", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_employee_cannot_create_expense_type(client, db_session):
    employee = await make_user(db_session, "EMPLOYEE")
    resp = await client.post("/expense-types", json={"code": "X", "name": "X", "category": "X"}, headers=bearer_headers(employee))
    assert resp.status_code == 403


async def test_auditor_manages_audit_rules(client, db_session):
    auditor = await make_user(db_session, "AUDITOR")
    headers = bearer_headers(auditor)
    payload = {"name": "Big Spend", "rule_type": "THRESHOLD", "threshold": "100", "severity": "WARNING"}

    created = await client.post("/audit-rules", json=payload, headers=headers)
    assert created.status_code == 201
    rule_id = created.json()["id"]

    assert (await client.get("/audit-rules", headers=headers)).status_code == 200

    updated = await client.put(f"/audit-rules/{rule_id}", json={**payload, "enabled": False}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    missing = await client.put("/audit-rules/00000000-0000-0000-0000-000000000000", json=payload, headers=headers)
    assert missing.status_code == 404


async def test_admin_creates_and_fetches_user(client, db_session):
    admin = await make_user(db_session, "ADMIN")
    headers = bearer_headers(admin)
    payload = {"employee_id": "EMP-NEW-1", "name": "New Hire", "email": "new@example-local.test",
               "department": "Sales", "password": "Password123!"}

    created = await client.post("/users", json=payload, headers=headers)
    assert created.status_code == 201
    user_id = created.json()["id"]

    fetched = await client.get(f"/users/{user_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["employee_id"] == "EMP-NEW-1"

    missing = await client.get("/users/00000000-0000-0000-0000-000000000000", headers=headers)
    assert missing.status_code == 404