import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.routes import (
    audit_rules,
    auth,
    expense_reports,
    expense_types,
    health,
    integrations,
    internal_mtls,
    reporting,
    users,
)
from app.core.config import get_settings

settings = get_settings()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

app = FastAPI(
    title="Enterprise Expense Integration Gateway",
    description=(
        "An independent educational implementation inspired by enterprise "
        "expense-management and integration concepts. Not an official SAP "
        "Concur product or integration."
    ),
    version="0.1.0",
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "correlation_id": "n/a"}},
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    correlation_id = request.headers.get(settings.correlation_id_header, str(uuid.uuid4()))
    started = time.monotonic()

    response = await call_next(request)

    duration_ms = int((time.monotonic() - started) * 1000)
    response.headers["X-Request-Id"] = request_id
    response.headers[settings.correlation_id_header] = correlation_id

    logger.info(
        "request_completed",
        request_id=request_id,
        correlation_id=correlation_id,
        endpoint=request.url.path,
        method=request.method,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(expense_types.router)
app.include_router(audit_rules.router)
app.include_router(expense_reports.router)
app.include_router(integrations.router)
app.include_router(reporting.router)
app.include_router(internal_mtls.router)
