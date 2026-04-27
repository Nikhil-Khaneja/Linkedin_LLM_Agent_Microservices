import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCatalog, http_error
from app.core.redis_client import redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.utils.helpers import generate_user_id

logger = logging.getLogger(__name__)


def check_login_rate_limit(email: str, max_attempts: int, window_seconds: int) -> None:
    key = f"auth:rl:login:{email}"
    current = redis_client.get(key)
    if current and int(current) >= max_attempts:
        raise http_error(429, ErrorCatalog.RATE_LIMITED)

    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    pipe.execute()


def clear_login_rate_limit(email: str) -> None:
    redis_client.delete(f"auth:rl:login:{email}")


def register_user(db: Session, email: str, password: str, user_type: str) -> dict:
    user = User(
        user_id=generate_user_id(),
        email=email,
        password_hash=hash_password(password),
        user_type=user_type,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise http_error(409, ErrorCatalog.DUPLICATE_EMAIL)

    access_token = create_access_token(user.user_id, user.email, user.user_type)
    refresh_token = create_refresh_token(user.user_id)

    db.add(RefreshToken(user_id=user.user_id, token=refresh_token, is_revoked=False))
    db.commit()

    logger.info("event=user.created user_id=%s email=%s", user.user_id, user.email)

    return {
        "user_id": user.user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 3600,
    }


def login_user(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise http_error(401, ErrorCatalog.INVALID_CREDENTIALS)

    access_token = create_access_token(user.user_id, user.email, user.user_type)
    refresh_token = create_refresh_token(user.user_id)

    db.add(RefreshToken(user_id=user.user_id, token=refresh_token, is_revoked=False))
    db.commit()

    return {
        "user_id": user.user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 3600,
    }


def refresh_user_token(db: Session, refresh_token: str) -> dict:
    stored = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if not stored or stored.is_revoked:
        raise http_error(401, ErrorCatalog.INVALID_REFRESH_TOKEN)

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise http_error(401, ErrorCatalog.INVALID_TOKEN_TYPE)

    user = db.query(User).filter(User.user_id == stored.user_id).first()
    if not user:
        raise http_error(404, ErrorCatalog.USER_NOT_FOUND)

    stored.is_revoked = True
    db.commit()

    new_access_token = create_access_token(user.user_id, user.email, user.user_type)
    new_refresh_token = create_refresh_token(user.user_id)

    db.add(RefreshToken(user_id=user.user_id, token=new_refresh_token, is_revoked=False))
    db.commit()

    return {
        "user_id": user.user_id,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_in": 3600,
    }


def logout_user(db: Session, refresh_token: str) -> dict:
    stored = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if stored:
        stored.is_revoked = True
        db.commit()
        logger.info("event=user.logout user_id=%s", stored.user_id)

    return {"message": "Logged out successfully"}