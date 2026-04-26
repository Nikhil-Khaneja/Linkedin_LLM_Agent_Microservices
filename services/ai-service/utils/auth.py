import os
import time
from typing import Optional

import httpx
from fastapi import HTTPException, Header
from jose import JWTError, jwt

JWKS_CACHE_TTL_SECONDS = int(os.getenv("JWKS_CACHE_TTL_SECONDS", "300"))
_jwks_cache: dict = {"keys": None, "expires_at": 0.0}


async def _fetch_jwks() -> dict:
    now = time.time()
    if _jwks_cache["keys"] and _jwks_cache["expires_at"] > now:
        return _jwks_cache["keys"]

    jwks_url = os.getenv("AUTH_SERVICE_JWKS_URL", "http://auth-service:3001/.well-known/jwks.json")
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()

    if not isinstance(jwks, dict) or "keys" not in jwks:
        raise HTTPException(status_code=503, detail="Invalid JWKS payload")

    _jwks_cache["keys"] = jwks
    _jwks_cache["expires_at"] = now + JWKS_CACHE_TTL_SECONDS
    return jwks


async def _decode_and_verify_token(token: str) -> Optional[dict]:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg", "RS256")
    except JWTError:
        return None

    jwks = await _fetch_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") != kid:
            continue
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
            if not user_id:
                return None
            return {"userId": user_id, "userType": payload.get("type")}
        except JWTError:
            return None
    return None


async def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[7:]
    decoded = await _decode_and_verify_token(token)
    if decoded:
        return decoded
    raise HTTPException(status_code=401, detail="Invalid token")


async def verify_ws_token(token: Optional[str]):
    if not token:
        return None
    return await _decode_and_verify_token(token)
