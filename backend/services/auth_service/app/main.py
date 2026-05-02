from fastapi import FastAPI

from services.auth_service.app.middleware.cors import setup_cors
from services.auth_service.app.routes.auth import router as auth_router
from services.auth_service.app.routes.gateway import router as gateway_router
from services.shared.observability import attach_observability

app = FastAPI(title='Auth Service')
setup_cors(app)
attach_observability(app, 'auth_service')
app.include_router(auth_router)
app.include_router(gateway_router)
