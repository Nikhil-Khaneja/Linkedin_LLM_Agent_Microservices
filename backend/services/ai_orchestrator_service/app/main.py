from fastapi import FastAPI
from services.ai_orchestrator_service.app.core.deps import get_ai_service
from services.ai_orchestrator_service.app.middleware.cors import setup_cors
from services.ai_orchestrator_service.app.routes.ai import router as ai_router
from services.shared.observability import attach_observability

app = FastAPI(title='AI Orchestrator Service')
setup_cors(app)
attach_observability(app, 'ai_orchestrator_service')
app.include_router(ai_router)

@app.on_event('startup')
async def startup() -> None:
    await get_ai_service().startup()

@app.on_event('shutdown')
async def shutdown() -> None:
    await get_ai_service().shutdown()
