from pydantic import BaseModel


class TokenRequest(BaseModel):
    username: str  # employee_id or email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
