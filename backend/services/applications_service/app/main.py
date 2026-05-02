from fastapi import FastAPI
from services.applications_service.app.core.deps import get_applications_service
from services.applications_service.app.middleware.cors import setup_cors
from services.applications_service.app.routes.applications import router as applications_router
from services.shared.observability import attach_observability

app = FastAPI(title='Applications Service')
setup_cors(app)
attach_observability(app, 'applications_service')
app.include_router(applications_router)

@app.on_event('startup')
async def startup() -> None:
    await get_applications_service().startup()

@app.on_event('shutdown')
async def shutdown() -> None:
    await get_applications_service().shutdown()
