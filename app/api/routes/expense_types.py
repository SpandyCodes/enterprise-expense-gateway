import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import UserRole
from app.models.expense import ExpenseType
from app.security.dependencies import get_current_claims, require_roles

router = APIRouter(tags=["expense-types"])


class ExpenseTypeIn(BaseModel):
    code: str
    name: str
    category: str
    default_currency: str = "USD"
    requires_receipt: bool = False
    active: bool = True


class ExpenseTypeOut(ExpenseTypeIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


@router.get("/expense-types", response_model=list[ExpenseTypeOut])
async def list_expense_types(db: AsyncSession = Depends(get_db), _=Depends(get_current_claims)):
    result = await db.execute(select(ExpenseType))
    return result.scalars().all()


@router.post("/expense-types", response_model=ExpenseTypeOut, status_code=201)
async def create_expense_type(payload: ExpenseTypeIn, db: AsyncSession = Depends(get_db), _=Depends(require_roles(UserRole.ADMIN))):
    etype = ExpenseType(**payload.model_dump())
    db.add(etype)
    await db.commit()
    await db.refresh(etype)
    return etype
