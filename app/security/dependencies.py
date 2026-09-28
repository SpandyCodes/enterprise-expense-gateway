"""
FastAPI dependencies for authentication and role-based authorization.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.security.jwt import TokenError, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _unauthorized(detail: str, correlation_id: str = "n/a") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHORIZED", "message": detail, "correlation_id": correlation_id}},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_claims(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        claims = decode_access_token(token)
    except TokenError as exc:
        raise _unauthorized(f"Invalid or expired token: {exc}") from exc
    if claims.get("token_type") != "access":
        raise _unauthorized("Wrong token type")
    return claims


def require_roles(*allowed_roles: str):
    """Dependency factory enforcing role-based access control."""

    async def _check(claims: dict = Depends(get_current_claims)) -> dict:
        role = claims.get("role")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Role '{role}' is not permitted to perform this action.",
                        "correlation_id": "n/a",
                    }
                },
            )
        return claims

    return _check
