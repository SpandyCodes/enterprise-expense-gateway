import pytest

pytestmark = pytest.mark.api


async def test_token_issued_for_valid_credentials(client, sample_employee):
    resp = await client.post("/auth/token", json={"username": sample_employee.employee_id, "password": "Password123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body


async def test_token_rejected_for_invalid_password(client, sample_employee):
    resp = await client.post("/auth/token", json={"username": sample_employee.employee_id, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
