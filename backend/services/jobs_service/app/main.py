from fastapi import FastAPI
from services.jobs_service.app.core.deps import get_jobs_service
from services.jobs_service.app.services.job_command_service import get_job_command_service
from services.jobs_service.app.middleware.cors import setup_cors
from services.jobs_service.app.routes.jobs import router as jobs_router
from services.shared.observability import attach_observability

app = FastAPI(title='Jobs Service')
setup_cors(app)
attach_observability(app, 'jobs_service')
app.include_router(jobs_router)

@app.on_event('startup')
async def startup() -> None:
    await get_jobs_service().startup()
    await get_job_command_service().startup()

@app.on_event('shutdown')
async def shutdown() -> None:
    await get_job_command_service().shutdown()
    await get_jobs_service().shutdown()
