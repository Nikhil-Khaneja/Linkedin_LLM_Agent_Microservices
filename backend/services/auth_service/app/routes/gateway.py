from fastapi import APIRouter, Depends, Header

from services.auth_service.app.core.deps import get_auth_service
from services.auth_service.app.schemas.auth import IdempotencyCheckRequest
from services.shared.common import check_idempotency, fail, require_auth, success, trace_id

router = APIRouter()


@router.post('/gateway/idempotency/check')
def check(payload: IdempotencyCheckRequest, authorization: str | None = Header(None), x_trace_id: str | None = Header(None), _auth_service=Depends(get_auth_service)):
    trc = trace_id(x_trace_id)
    try:
        require_auth(authorization)
    except Exception:
        return fail('auth_required', 'Bearer token is missing or invalid.', trc, status_code=401)
    record, conflict = check_idempotency(payload.route, payload.idempotency_key, payload.body_hash)
    if not record and not conflict:
        return success({'reusable': True, 'status': 'missing'}, trc)
    if conflict:
        return success({'reusable': False, 'status': 'conflict'}, trc)
    return success({'reusable': False, 'status': 'completed', 'original_trace_id': record.get('trace_id', 'trc_original')}, trc)
