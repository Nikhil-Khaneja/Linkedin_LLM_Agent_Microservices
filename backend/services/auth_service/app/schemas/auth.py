from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    user_type: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    access_level: str | None = None
    idempotency_key: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class IdempotencyCheckRequest(BaseModel):
    route: str
    idempotency_key: str
    body_hash: str
