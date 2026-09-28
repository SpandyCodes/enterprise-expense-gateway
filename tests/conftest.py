"""
Shared fixtures.

DB-backed fixtures (`db_session`, `client`) require a running PostgreSQL
instance reachable via TEST_DATABASE_URL (defaults to the docker-compose
postgres service with a dedicated `test` database/schema so tests never
touch development data). Pure unit tests that don't need `db_session`
run without any database at all.
"""
import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://expense_user:expense_pw@localhost:5432/expense_gateway_test"),
)

from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security.jwt import create_access_token, hash_password  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    from app.core.database import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_employee(db_session):
    user = User(
        employee_id=f"EMP{uuid.uuid4().hex[:6]}",
        name="Test Employee",
        email=f"employee-{uuid.uuid4().hex[:6]}@example-local.test",
        department="Engineering",
        role="EMPLOYEE",
        hashed_password=hash_password("Password123!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_manager(db_session):
    user = User(
        employee_id=f"MGR{uuid.uuid4().hex[:6]}",
        name="Test Manager",
        email=f"manager-{uuid.uuid4().hex[:6]}@example-local.test",
        department="Engineering",
        role="MANAGER",
        hashed_password=hash_password("Password123!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def bearer_headers(user) -> dict:
    token = create_access_token(subject=str(user.id), role=user.role, extra_claims={"employee_id": user.employee_id})
    return {"Authorization": f"Bearer {token}"}
