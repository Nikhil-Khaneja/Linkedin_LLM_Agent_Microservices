import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.errors import ErrorCatalog
from app.db.session import SessionLocal
from app.services.idempotency_service import (
    create_idempotency_record,
    get_idempotency_record,
    save_idempotency_response,
)
from app.utils.helpers import build_request_hash


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
IDEMPOTENT_PATHS = {
    "/auth/register",
    "/auth/logout",
}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS or request.url.path not in IDEMPOTENT_PATHS:
            return await call_next(request)

        idem_key = request.headers.get("idempotency-key")
        if not idem_key:
            return await call_next(request)

        body_bytes = await request.body()
        payload_dict = {}
        if body_bytes:
            try:
                payload_dict = json.loads(body_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                payload_dict = {"raw": body_bytes.decode("utf-8", errors="ignore")}

        request_hash = build_request_hash(payload_dict)

        db = SessionLocal()
        try:
            existing = get_idempotency_record(db, idem_key)
            if existing:
                if existing.request_hash != request_hash:
                    code, message = ErrorCatalog.IDEMPOTENCY_CONFLICT
                    return JSONResponse(
                        status_code=409,
                        content={"detail": {"code": code, "message": message}},
                    )
                return JSONResponse(
                    status_code=existing.status_code or 200,
                    content=json.loads(existing.response_body) if existing.response_body else {
                        "message": "Duplicate request detected"
                    },
                    headers={"x-idempotent-replay": "true"},
                )

            create_idempotency_record(
                db=db,
                idem_key=idem_key,
                request_hash=request_hash,
                method=request.method,
                path=request.url.path,
            )

            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request = Request(request.scope, receive)
            response = await call_next(request)

            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            response_text = response_body.decode("utf-8") if response_body else "{}"

            stored = get_idempotency_record(db, idem_key)
            if stored:
                save_idempotency_response(
                    db=db,
                    row=stored,
                    status_code=response.status_code,
                    response_body=response_text,
                )

            return JSONResponse(
                status_code=response.status_code,
                content=json.loads(response_text) if response_text else {},
                headers=dict(response.headers),
            )
        finally:
            db.close()