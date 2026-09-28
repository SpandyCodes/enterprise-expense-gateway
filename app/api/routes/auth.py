from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import api_error
from app.models.user import User
from app.schemas.auth import TokenRequest, TokenResponse
from app.security.jwt import create_access_token, verify_password
from app.core.config import get_settings

router = APIRouter(tags=["auth"])
settings = get_settings()


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where((User.employee_id == payload.username) | (User.email == payload.username))
    )
    user = result.scalars().first()
    if not user or not user.active or not verify_password(payload.password, user.hashed_password):
        raise api_error(401, "INVALID_CREDENTIALS", "Invalid username or password")

    token = create_access_token(subject=str(user.id), role=user.role, extra_claims={"employee_id": user.employee_id})
    return TokenResponse(access_token=token, expires_in=settings.jwt_access_token_expire_minutes * 60)
