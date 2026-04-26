from fastapi import HTTPException, status


class ErrorCatalog:
    DUPLICATE_EMAIL = ("AUTH_409_DUPLICATE_EMAIL", "Email already exists")
    INVALID_CREDENTIALS = ("AUTH_401_INVALID_CREDENTIALS", "Invalid credentials")
    INVALID_REFRESH_TOKEN = ("AUTH_401_INVALID_REFRESH", "Invalid refresh token")
    INVALID_TOKEN_TYPE = ("AUTH_401_INVALID_TOKEN_TYPE", "Invalid token type")
    USER_NOT_FOUND = ("AUTH_404_USER_NOT_FOUND", "User not found")
    MISSING_TOKEN = ("AUTH_401_MISSING_TOKEN", "Authorization token missing")
    INVALID_ACCESS_TOKEN = ("AUTH_401_INVALID_ACCESS_TOKEN", "Invalid access token")
    RATE_LIMITED = ("AUTH_429_RATE_LIMITED", "Too many login attempts")
    IDEMPOTENCY_CONFLICT = (
        "AUTH_409_IDEMPOTENCY_CONFLICT",
        "Idempotency key reused with different payload",
    )


def http_error(status_code: int, code_message: tuple[str, str]) -> HTTPException:
    code, message = code_message
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})