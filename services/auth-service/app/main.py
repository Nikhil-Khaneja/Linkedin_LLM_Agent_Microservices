from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.gateway import router as gateway_router
from app.api.routes.protected import router as protected_router
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.middleware.auth_context import AuthContextMiddleware
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.request_context import RequestContextMiddleware

configure_logging()
init_db()

app = FastAPI(title="Owner1 Auth + API Edge", version="1.0.0")

app.add_middleware(RequestContextMiddleware)
app.add_middleware(AuthContextMiddleware)
app.add_middleware(IdempotencyMiddleware)

app.include_router(auth_router)
app.include_router(gateway_router)
app.include_router(protected_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "owner1-auth"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "AUTH_500_INTERNAL_ERROR",
                "message": "Internal server error",
            }
        },
    )