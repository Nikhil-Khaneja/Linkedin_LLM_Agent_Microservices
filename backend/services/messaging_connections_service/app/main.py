from fastapi import FastAPI
from services.messaging_connections_service.app.core.deps import get_messaging_service
from services.messaging_connections_service.app.middleware.cors import setup_cors
from services.messaging_connections_service.app.routes.messaging import router as messaging_router
from services.shared.observability import attach_observability

app = FastAPI(title='Messaging Connections Service')
setup_cors(app)
attach_observability(app, 'messaging_connections_service')
app.include_router(messaging_router)

@app.on_event('startup')
async def startup() -> None:
    await get_messaging_service().startup()

@app.on_event('shutdown')
async def shutdown() -> None:
    await get_messaging_service().shutdown()
