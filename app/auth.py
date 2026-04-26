"""
auth.py — Bearer token authentication dependency for Owner 5 Application Service.

All /applications/* endpoints require:
    Authorization: Bearer <API_BEARER_TOKEN>

The token is read from the API_BEARER_TOKEN environment variable.
In standalone demo mode the default value "owner5-demo-token" is used.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import API_BEARER_TOKEN

_bearer_scheme = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    Validates the Bearer token against API_BEARER_TOKEN from config.
    Raises HTTP 401 if the token is missing or does not match.
    Returns the token string on success.
    """
    if credentials.credentials != API_BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
