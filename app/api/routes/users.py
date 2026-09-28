import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import not_found
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.expense import UserCreate, UserOut
from app.security.dependencies import require_roles
from app.security.jwt import hash_password

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _=Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR))):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_roles(*[r.value for r in UserRole]))):
    user = await db.get(User, user_id)
    if not user:
        raise not_found(f"User {user_id} not found")
    return user


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db), _=Depends(require_roles(UserRole.ADMIN))):
    user = User(
        employee_id=payload.employee_id,
        name=payload.name,
        email=payload.email,
        department=payload.department,
        manager_id=payload.manager_id,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
