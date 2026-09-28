"""
Idempotency-Key handling for POST /integrations/expenses.

If the same key is seen twice with the same request body, the previously
stored response is replayed instead of re-processing the request. If the
same key is seen with a *different* body, this is treated as a client
error (key reuse across different requests).
"""
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IdempotencyRecord


def hash_request(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyKeyConflict(Exception):
    """Same Idempotency-Key reused with a different request body."""


async def get_existing(session: AsyncSession, idempotency_key: str) -> IdempotencyRecord | None:
    result = await session.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key)
    )
    return result.scalars().first()


async def check_or_reserve(
    session: AsyncSession, idempotency_key: str, endpoint: str, body: dict[str, Any]
) -> IdempotencyRecord | None:
    """Returns an existing record if this exact request was already
    processed (caller should replay its stored response), or None if
    this is a new request that should proceed normally."""
    request_hash = hash_request(body)
    existing = await get_existing(session, idempotency_key)
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        raise IdempotencyKeyConflict(
            f"Idempotency-Key '{idempotency_key}' was already used with a different request body"
        )
    return existing


async def store_response(
    session: AsyncSession, idempotency_key: str, endpoint: str, body: dict[str, Any], status_code: int, response_body: dict[str, Any]
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        idempotency_key=idempotency_key,
        endpoint=endpoint,
        request_hash=hash_request(body),
        response_status=status_code,
        response_body=response_body,
    )
    session.add(record)
    return record
