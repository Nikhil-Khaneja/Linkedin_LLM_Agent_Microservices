from fastapi import APIRouter, Body, Depends, Header
from services.applications_service.app.core.deps import get_applications_service
from services.shared.common import trace_id

router = APIRouter()

@router.post('/applications/submit')
async def submit(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), idempotency_key: str | None = Header(None), svc=Depends(get_applications_service)):
    return await svc.submit(payload, authorization, trace_id(x_trace_id), idempotency_key)

@router.post('/applications/start')
def start_application(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_applications_service)):
    return svc.start_application(payload, authorization, trace_id(x_trace_id))

@router.post('/applications/get')
def get_application(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_applications_service)):
    return svc.get_application(payload, authorization, trace_id(x_trace_id))

@router.post('/applications/byJob')
def by_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_applications_service)):
    return svc.by_job(payload, authorization, trace_id(x_trace_id))

@router.post('/applications/byMember')
def by_member(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_applications_service)):
    return svc.by_member(payload, authorization, trace_id(x_trace_id))

@router.post('/applications/updateStatus')
async def update_status(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), idempotency_key: str | None = Header(None), svc=Depends(get_applications_service)):
    return await svc.update_status(payload, authorization, trace_id(x_trace_id), idempotency_key)

@router.post('/applications/addNote')
def add_note(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_applications_service)):
    return svc.add_note(payload, authorization, trace_id(x_trace_id))
