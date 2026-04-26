from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    user_type: Literal["member", "recruiter"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    expires_in: int


class IdempotencyCheckRequest(BaseModel):
    idempotency_key: str
    request_hash: str


class IdempotencyCheckResponse(BaseModel):
    safe_to_process: bool
    message: str
    cached_response: Optional[str] = None


class TokenPayload(BaseModel):
    sub: str
    email: Optional[str] = None
    user_type: Optional[str] = None
    type: str
    iss: str
    aud: str
    exp: int
    iat: int
    jti: Optional[str] = None