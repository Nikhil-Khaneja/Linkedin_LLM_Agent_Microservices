from fastapi import APIRouter, Body, Depends, Header

from services.auth_service.app.core.deps import get_auth_service
from services.auth_service.app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest
from services.shared.common import JWKS, fail, require_auth, success, trace_id

router = APIRouter()


@router.post('/auth/register')
async def register(payload: RegisterRequest, x_trace_id: str | None = Header(None), idempotency_key: str | None = Header(None), auth_service=Depends(get_auth_service)):
    trc = trace_id(x_trace_id)
    data = payload.model_dump()
    if data.get('user_type') not in {'member', 'recruiter'}:
        return fail('validation_error', 'Missing or invalid register fields.', trc, status_code=400)
    result = await auth_service.register(data, trc, idempotency_key)
    if result['kind'] == 'error':
        return fail(result['code'], result['message'], trc, result.get('details'), result.get('retryable', False), result['status_code'])
    return success(result['data'], result['trace_id'], result.get('meta'))


@router.post('/auth/login')
def login(payload: LoginRequest, x_trace_id: str | None = Header(None), auth_service=Depends(get_auth_service)):
    trc = trace_id(x_trace_id)
    result = auth_service.login(payload.email, payload.password, trc)
    if result['kind'] == 'error':
        return fail(result['code'], result['message'], trc, result.get('details'), result.get('retryable', False), result['status_code'])
    return success(result['data'], result['trace_id'])


@router.post('/auth/refresh')
def refresh(payload: RefreshRequest, x_trace_id: str | None = Header(None), auth_service=Depends(get_auth_service)):
    trc = trace_id(x_trace_id)
    result = auth_service.refresh(payload.refresh_token, trc)
    if result['kind'] == 'error':
        return fail(result['code'], result['message'], trc, status_code=result['status_code'])
    return success(result['data'], result['trace_id'])


@router.post('/auth/logout')
def logout(payload: LogoutRequest, authorization: str | None = Header(None), x_trace_id: str | None = Header(None), auth_service=Depends(get_auth_service)):
    trc = trace_id(x_trace_id)
    try:
        require_auth(authorization)
    except Exception:
        return fail('auth_required', 'Bearer token is missing or invalid.', trc, status_code=401)
    result = auth_service.logout(payload.refresh_token, trc)
    return success(result['data'], result['trace_id'])


@router.get('/.well-known/jwks.json')
def jwks(x_trace_id: str | None = Header(None)):
    return success(JWKS, trace_id(x_trace_id))
