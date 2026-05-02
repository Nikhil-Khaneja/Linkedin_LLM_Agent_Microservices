from fastapi import APIRouter, Body, Depends, Header
from services.recruiter_company_service.app.core.deps import get_recruiter_service
from services.shared.common import trace_id

router = APIRouter()

@router.post('/recruiters/create')
def create_recruiter(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.create_recruiter(payload, authorization, trace_id(x_trace_id))

@router.post('/recruiters/get')
def get_recruiter(payload: dict = Body(default={}), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.get_recruiter(payload, authorization, trace_id(x_trace_id))


@router.post('/recruiters/publicGet')
def public_get_recruiter(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.public_get_recruiter(payload, authorization, trace_id(x_trace_id))

@router.post('/recruiters/update')
def update_recruiter(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.update_recruiter(payload, authorization, trace_id(x_trace_id))

@router.post('/companies/create')
def create_company(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.create_company(payload, authorization, trace_id(x_trace_id))

@router.post('/companies/update')
def update_company(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.update_company(payload, authorization, trace_id(x_trace_id))

@router.post('/companies/get')
def get_company(payload: dict = Body(default={}), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_recruiter_service)):
    return svc.get_company(payload, authorization, trace_id(x_trace_id))
