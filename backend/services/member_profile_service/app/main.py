from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from services.member_profile_service.app.middleware.cors import setup_cors
from services.member_profile_service.app.routes.members import router as members_router
from services.member_profile_service.app.services.media_upload_service import get_media_upload_service
from services.member_profile_service.app.services.member_event_projection_service import get_member_event_projection_service
from services.member_profile_service.app.services.member_command_service import get_member_command_service
from services.shared.observability import attach_observability

app = FastAPI(title='Member Profile Service')
setup_cors(app)
attach_observability(app, 'member_profile_service')
app.include_router(members_router)

UPLOAD_DIR = Path(os.environ.get('APP_DATA_DIR', '/app/data')) / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/static/uploads', StaticFiles(directory=str(UPLOAD_DIR)), name='member_uploads')


@app.on_event('startup')
async def startup() -> None:
    await get_media_upload_service().startup()
    await get_member_event_projection_service().startup()
    await get_member_command_service().startup()


@app.on_event('shutdown')
async def shutdown() -> None:
    await get_member_command_service().shutdown()
    await get_member_event_projection_service().shutdown()
    await get_media_upload_service().shutdown()
