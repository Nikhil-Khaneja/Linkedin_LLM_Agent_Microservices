from fastapi import APIRouter, Body, Depends, Header, WebSocket
from services.ai_orchestrator_service.app.core.deps import get_ai_service
from services.shared.common import trace_id

router = APIRouter()

@router.post('/ai/tasks/create')
async def create_task(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), idempotency_key: str | None = Header(None), svc=Depends(get_ai_service)):
    return await svc.create_task(payload, authorization, trace_id(x_trace_id), idempotency_key)

@router.get('/ai/tasks')
def list_tasks(authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return svc.list_tasks(authorization, trace_id(x_trace_id))

@router.get('/ai/analytics/approval-rate')
def approval_rate(authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return svc.approval_rate(authorization, trace_id(x_trace_id))

@router.get('/ai/analytics/match-quality')
def match_quality(authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return svc.match_quality(authorization, trace_id(x_trace_id))

@router.post('/ai/coach/suggest')
async def coach_suggest(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return await svc.coach_suggest(payload, authorization, trace_id(x_trace_id))

@router.get('/ai/tasks/{task_id}')
def get_task(task_id: str, authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return svc.get_task(task_id, authorization, trace_id(x_trace_id))

@router.post('/ai/tasks/{task_id}/approve')
async def approve_task(task_id: str, payload: dict = Body(default={}), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return await svc.approve_task(task_id, payload, authorization, trace_id(x_trace_id))

@router.post('/ai/tasks/{task_id}/reject')
async def reject_task(task_id: str, payload: dict = Body(default={}), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return await svc.reject_task(task_id, payload, authorization, trace_id(x_trace_id))


@router.post('/ai/tasks/{task_id}/sendOutreach')
async def send_outreach(task_id: str, payload: dict = Body(default={}), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_ai_service)):
    return await svc.send_outreach(task_id, payload, authorization, trace_id(x_trace_id))

@router.websocket('/ws/ai/tasks/{task_id}')
async def task_socket(websocket: WebSocket, task_id: str):
    svc = get_ai_service()
    await svc.task_socket(websocket, task_id)
