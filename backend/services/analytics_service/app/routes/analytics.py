from fastapi import APIRouter, Body, Depends, Header
from services.analytics_service.app.core.deps import get_analytics_service
from services.shared.common import trace_id

router = APIRouter()

@router.post('/events/ingest')
async def ingest(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return await svc.ingest(payload, authorization, trace_id(x_trace_id))

@router.post('/analytics/jobs/top')
def top_jobs(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return svc.top_jobs(payload, authorization, trace_id(x_trace_id))

@router.post('/analytics/funnel')
def funnel(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return svc.funnel(payload, authorization, trace_id(x_trace_id))

@router.post('/analytics/geo')
def geo(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return svc.geo(payload, authorization, trace_id(x_trace_id))

@router.post('/analytics/member/dashboard')
def member_dashboard(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return svc.member_dashboard(payload, authorization, trace_id(x_trace_id))

@router.post('/benchmarks/report')
async def benchmarks(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return await svc.benchmarks(payload, authorization, trace_id(x_trace_id))


@router.post('/benchmarks/list')
def list_benchmarks(payload: dict = Body(default={}), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_analytics_service)):
    return svc.list_benchmarks(payload, authorization, trace_id(x_trace_id))
