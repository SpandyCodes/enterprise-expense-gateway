import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import UserRole
from app.security.dependencies import require_roles

router = APIRouter(tags=["reporting"])

_ROLE_DEP = require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.MANAGER)


@router.get("/reports/expenses/summary")
async def expenses_summary(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(text("SELECT * FROM expense_summary"))
    return [dict(row._mapping) for row in result]


@router.get("/reports/expenses/by-category")
async def expenses_by_category(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(text("SELECT * FROM expense_by_type"))
    return [dict(row._mapping) for row in result]


@router.get("/reports/expenses/by-department")
async def expenses_by_department(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(text("SELECT * FROM expense_by_department"))
    return [dict(row._mapping) for row in result]


@router.get("/reports/expenses/audit-exceptions")
async def audit_exceptions(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(text("SELECT * FROM audit_exception_summary"))
    return [dict(row._mapping) for row in result]


@router.get("/reports/integrations/failures")
async def integration_failures(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(text("SELECT * FROM integration_failure_summary"))
    return [dict(row._mapping) for row in result]


@router.get("/reports/export/csv")
async def export_csv(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(text("SELECT * FROM expense_summary"))
    rows = [dict(row._mapping) for row in result]

    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expense_summary.csv"},
    )
