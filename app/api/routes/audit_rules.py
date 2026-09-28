import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import not_found
from app.models.approval_audit import AuditRule
from app.models.enums import Severity, UserRole
from app.security.dependencies import require_roles

router = APIRouter(tags=["audit-rules"])


class AuditRuleIn(BaseModel):
    name: str
    description: str | None = None
    rule_type: str
    threshold: Decimal | None = None
    severity: Severity = Severity.WARNING
    enabled: bool = True
    configuration: dict = {}


class AuditRuleOut(AuditRuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


_ROLE_DEP = require_roles(UserRole.AUDITOR, UserRole.ADMIN)


@router.get("/audit-rules", response_model=list[AuditRuleOut])
async def list_audit_rules(db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    result = await db.execute(select(AuditRule))
    return result.scalars().all()


@router.post("/audit-rules", response_model=AuditRuleOut, status_code=201)
async def create_audit_rule(payload: AuditRuleIn, db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    rule = AuditRule(**payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/audit-rules/{rule_id}", response_model=AuditRuleOut)
async def update_audit_rule(rule_id: uuid.UUID, payload: AuditRuleIn, db: AsyncSession = Depends(get_db), _=Depends(_ROLE_DEP)):
    rule = await db.get(AuditRule, rule_id)
    if not rule:
        raise not_found(f"Audit rule {rule_id} not found")
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule
