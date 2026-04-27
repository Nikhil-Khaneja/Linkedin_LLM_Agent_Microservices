from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.errors import ErrorCatalog, http_error
from app.core.security import get_public_jwks
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import (
    check_login_rate_limit,
    clear_login_rate_limit,
    login_user,
    logout_user,
    refresh_user_token,
    register_user,
)

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(db, payload.email, payload.password, payload.user_type)


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    check_login_rate_limit(
        email=payload.email,
        max_attempts=settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    result = login_user(db, payload.email, payload.password)
    clear_login_rate_limit(payload.email)
    return result


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return refresh_user_token(db, payload.refresh_token)


@router.post("/auth/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    return logout_user(db, payload.refresh_token)


@router.get("/.well-known/jwks.json")
def jwks():
    return get_public_jwks()