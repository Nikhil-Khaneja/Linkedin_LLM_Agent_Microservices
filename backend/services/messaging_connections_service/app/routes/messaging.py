from fastapi import APIRouter, Body, Depends, Header
from services.messaging_connections_service.app.core.deps import get_messaging_service
from services.shared.common import trace_id

router = APIRouter()

@router.post('/threads/open')
async def open_thread(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return await svc.open_thread(payload, authorization, trace_id(x_trace_id))

@router.post('/threads/get')
def get_thread(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.get_thread(payload, authorization, trace_id(x_trace_id))

@router.post('/threads/byUser')
def threads_by_user(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.threads_by_user(payload, authorization, trace_id(x_trace_id))

@router.post('/messages/list')
def list_messages(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.list_messages(payload, authorization, trace_id(x_trace_id))

@router.post('/messages/send')
async def send_message(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), idempotency_key: str | None = Header(None), svc=Depends(get_messaging_service)):
    return await svc.send_message(payload, authorization, trace_id(x_trace_id), idempotency_key)

@router.post('/connections/request')
async def request_connection(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return await svc.request_connection(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/accept')
async def accept_connection(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return await svc.accept_connection(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/reject')
async def reject_connection(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return await svc.reject_connection(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/list')
def list_connections(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.list_connections(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/mutual')
def mutual_connections(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.mutual_connections(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/sent')
def sent_connections(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.sent_connections(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/withdraw')
async def withdraw_connection(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return await svc.withdraw_connection(payload, authorization, trace_id(x_trace_id))

@router.post('/connections/pending')
def pending_connections(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None), svc=Depends(get_messaging_service)):
    return svc.pending_connections(payload, authorization, trace_id(x_trace_id))
