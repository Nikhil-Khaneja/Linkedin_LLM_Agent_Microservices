from fastapi import APIRouter, Body, Depends, Header
from services.jobs_service.app.core.deps import get_jobs_service
from services.shared.common import trace_id

router = APIRouter()

@router.post('/jobs/create')
async def create_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return await svc.create_job(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/get')
def get_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return svc.get_job(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/update')
async def update_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return await svc.update_job(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/search')
def search_jobs(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return svc.search_jobs(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/close')
async def close_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return await svc.close_job(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/byRecruiter')
def jobs_by_recruiter(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return svc.jobs_by_recruiter(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/save')
async def save_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return await svc.save_job(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/unsave')
async def unsave_job(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return await svc.unsave_job(payload, authorization, trace_id(x_trace_id))

@router.post('/jobs/savedByMember')
def saved_jobs(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_jobs_service)):
    return svc.saved_jobs(payload, authorization, trace_id(x_trace_id))
