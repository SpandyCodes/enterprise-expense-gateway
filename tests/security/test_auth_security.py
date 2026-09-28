from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import get_settings
from tests.conftest import bearer_headers

pytestmark = pytest.mark.security

settings = get_settings()


async def test_missing_bearer_token_returns_401(client):
    resp = await client.get("/users")
    assert resp.status_code == 401


async def test_invalid_token_returns_401(client):
    resp = await client.get("/users", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


async def test_expired_token_returns_401(client, sample_employee):
    payload = {
        "sub": str(sample_employee.id),
        "role": sample_employee.role,
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "token_type": "access",
    }
    expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    resp = await client.get("/users", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


async def test_insufficient_role_returns_403(client, sample_employee):
    # EMPLOYEE role is not permitted to list all users (ADMIN/MANAGER/AUDITOR only)
    headers = bearer_headers(sample_employee)
    resp = await client.get("/users", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_manager_role_can_list_users(client, sample_manager):
    headers = bearer_headers(sample_manager)
    resp = await client.get("/users", headers=headers)
    assert resp.status_code == 200
