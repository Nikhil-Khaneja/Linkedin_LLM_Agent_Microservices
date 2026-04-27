from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import try_decode_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("authorization")
        request.state.user = None

        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            payload = try_decode_token(token)
            if payload and payload.get("type") == "access":
                request.state.user = payload

        return await call_next(request)