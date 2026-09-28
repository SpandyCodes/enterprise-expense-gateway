import time
import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import bad_request, not_found
from app.integrations.adapter import AdapterValidationError, ExternalExpenseAdapter
from app.integrations.idempotency import IdempotencyKeyConflict, check_or_reserve, store_response
from app.models.enums import UserRole
from app.models.integration import IntegrationLog
from app.security.dependencies import require_roles

router = APIRouter(tags=["integrations"])


@router.post("/integrations/expenses", status_code=202)
async def ingest_expense(
    request: Request,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _=Depends(require_roles(UserRole.INTEGRATION_SERVICE, UserRole.ADMIN)),
):
    correlation_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    started = time.monotonic()
    body = await request.json()

    if not idempotency_key:
        raise bad_request("Idempotency-Key header is required", correlation_id)

    try:
        existing = await check_or_reserve(db, idempotency_key, "/integrations/expenses", body)
    except IdempotencyKeyConflict as exc:
        raise bad_request(str(exc), correlation_id) from exc

    if existing is not None:
        # Replay the previously stored response — no reprocessing, no duplicate data.
        return existing.response_body

    log = IntegrationLog(
        correlation_id=correlation_id,
        request_id=request_id,
        source_system="external_expense_system",
        target_system="expense_gateway",
        endpoint="/integrations/expenses",
        http_method="POST",
        status="PROCESSING",
        retry_count=0,
    )
    db.add(log)

    try:
        internal = ExternalExpenseAdapter.adapt(body)
    except AdapterValidationError as exc:
        log.status = "FAILED"
        log.error_code = "VALIDATION_ERROR"
        log.error_message = str(exc.errors)
        log.duration_ms = int((time.monotonic() - started) * 1000)
        await db.commit()
        raise bad_request(f"Payload validation failed: {exc.errors}", correlation_id) from exc

    response_body = {
        "correlation_id": correlation_id,
        "status": "ACCEPTED",
        "internal_expense": internal.model_dump(mode="json"),
    }

    log.status = "SUCCEEDED"
    log.duration_ms = int((time.monotonic() - started) * 1000)
    await store_response(db, idempotency_key, "/integrations/expenses", body, 202, response_body)
    await db.commit()

    return response_body


@router.get("/integrations/{correlation_id}")
async def get_integration(correlation_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_roles(UserRole.INTEGRATION_SERVICE, UserRole.ADMIN, UserRole.AUDITOR))):
    result = await db.execute(select(IntegrationLog).where(IntegrationLog.correlation_id == correlation_id))
    logs = result.scalars().all()
    if not logs:
        raise not_found(f"No integration logs found for correlation_id {correlation_id}")
    return logs


@router.get("/integrations/logs")
async def list_integration_logs(db: AsyncSession = Depends(get_db), _=Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    result = await db.execute(select(IntegrationLog).order_by(IntegrationLog.created_at.desc()).limit(200))
    return result.scalars().all()
