import os
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.jwks import rsa_public_key_to_jwk

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _ensure_keys():
    if os.path.exists(settings.PRIVATE_KEY_PATH) and os.path.exists(settings.PUBLIC_KEY_PATH):
        with open(settings.PRIVATE_KEY_PATH, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(settings.PUBLIC_KEY_PATH, "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())
        return private_key, public_key

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    with open(settings.PRIVATE_KEY_PATH, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    with open(settings.PUBLIC_KEY_PATH, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    return private_key, public_key


_PRIVATE_KEY_OBJ, _PUBLIC_KEY_OBJ = _ensure_keys()

PRIVATE_KEY_PEM = _PRIVATE_KEY_OBJ.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

PUBLIC_KEY_PEM = _PUBLIC_KEY_OBJ.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()


def get_public_jwks() -> dict:
    return {"keys": [rsa_public_key_to_jwk(_PUBLIC_KEY_OBJ, settings.JWKS_KID)]}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, email: str, user_type: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "user_type": user_type,
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        PRIVATE_KEY_PEM,
        algorithm=settings.JWT_ALGORITHM,
        headers={"kid": settings.JWKS_KID},
    )


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        PRIVATE_KEY_PEM,
        algorithm=settings.JWT_ALGORITHM,
        headers={"kid": settings.JWKS_KID},
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        PUBLIC_KEY_PEM,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
    )


def try_decode_token(token: str) -> dict | None:
    try:
        return decode_token(token)
    except JWTError:
        return None