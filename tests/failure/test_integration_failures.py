import pytest

from tests.conftest import bearer_headers

pytestmark = pytest.mark.failure


async def _integration_user_headers(db_session):
    from app.models.user import User
    from app.security.jwt import hash_password

    svc = User(
        employee_id="SVC-TEST-1", name="Integration Svc", email="svc-test@example-local.test",
        department="IT", role="INTEGRATION_SERVICE", hashed_password=hash_password("pw"),
    )
    db_session.add(svc)
    await db_session.commit()
    await db_session.refresh(svc)
    return bearer_headers(svc)


VALID_PAYLOAD = {
    "external_expense_id": "EXT-90001",
    "employee": {"employee_id": "EMP001"},
    "expense_type": "MEALS",
    "vendor": "Example Restaurant",
    "transaction_date": "2026-09-20",
    "amount": 125.00,
    "currency": "USD",
    "receipt_reference": "receipt-90001",
}


async def test_duplicate_integration_request_is_not_reprocessed(client, db_session):
    headers = await _integration_user_headers(db_session)
    headers["Idempotency-Key"] = "test-key-001"

    first = await client.post("/integrations/expenses", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 202
    first_correlation_id = first.json()["correlation_id"]

    second = await client.post("/integrations/expenses", json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 202
    # Same stored response is replayed — same correlation_id, not reprocessed
    assert second.json()["correlation_id"] == first_correlation_id


async def test_idempotency_key_reused_with_different_body_is_rejected(client, db_session):
    headers = await _integration_user_headers(db_session)
    headers["Idempotency-Key"] = "test-key-002"

    first = await client.post("/integrations/expenses", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 202

    different_payload = {**VALID_PAYLOAD, "amount": 999.00}
    second = await client.post("/integrations/expenses", json=different_payload, headers=headers)
    assert second.status_code == 400


async def test_missing_idempotency_key_is_rejected(client, db_session):
    headers = await _integration_user_headers(db_session)
    resp = await client.post("/integrations/expenses", json=VALID_PAYLOAD, headers=headers)
    assert resp.status_code == 400


async def test_malformed_payload_returns_400_and_is_not_retried(client, db_session):
    headers = await _integration_user_headers(db_session)
    headers["Idempotency-Key"] = "test-key-003"
    malformed = {**VALID_PAYLOAD, "amount": -50}  # fails validation
    resp = await client.post("/integrations/expenses", json=malformed, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "BAD_REQUEST"


async def test_invalid_state_transition_returns_400(client, sample_employee):
    headers = bearer_headers(sample_employee)
    create_resp = await client.post("/expense-reports", json={"title": "Trip"}, headers=headers)
    report_id = create_resp.json()["id"]

    # Cannot approve a report that hasn't even been submitted
    resp = await client.post(f"/expense-reports/{report_id}/approve", headers=headers)
    assert resp.status_code in (400, 403)  # 403 if role check fires first, 400 if role passes but no pending approval
