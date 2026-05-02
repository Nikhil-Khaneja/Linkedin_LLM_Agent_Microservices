from fastapi import FastAPI
from services.analytics_service.app.core.deps import get_analytics_service
from services.analytics_service.app.middleware.cors import setup_cors
from services.analytics_service.app.routes.analytics import router as analytics_router
from services.shared.observability import attach_observability

app = FastAPI(title='Analytics Service')
setup_cors(app)
attach_observability(app, 'analytics_service')
app.include_router(analytics_router)

@app.on_event('startup')
async def startup() -> None:
    await get_analytics_service().startup()

@app.on_event('shutdown')
async def shutdown() -> None:
    await get_analytics_service().shutdown()
