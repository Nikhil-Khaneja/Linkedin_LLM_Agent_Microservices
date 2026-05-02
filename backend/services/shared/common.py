from __future__ import annotations

import contextvars
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import jwt

from services.shared.auth import current_jwks, verify_bearer_token

JWKS = current_jwks()
IDEMPOTENCY = {}
CURRENT_TRACE_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar('current_trace_id', default=None)
CURRENT_SERVICE: contextvars.ContextVar[str | None] = contextvars.ContextVar('current_service', default=None)


def service_name(explicit: str | None = None) -> str:
    if explicit:
        CURRENT_SERVICE.set(explicit)
        return explicit
    return CURRENT_SERVICE.get() or os.environ.get('SERVICE_NAME', 'unknown-service')


def set_trace(trace: str | None) -> str:
    value = trace or f'trc_{uuid4()}'
    CURRENT_TRACE_ID.set(value)
    return value


def clear_trace() -> None:
    CURRENT_TRACE_ID.set(None)


def trace_id(value: Optional[str] = None) -> str:
    if value:
        return set_trace(value)
    current = CURRENT_TRACE_ID.get()
    if current:
        return current
    return set_trace(None)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def success(data, trace: Optional[str] = None, meta=None, status_code: int = 200):
    payload = {'success': True, 'trace_id': trace_id(trace), 'data': data}
    if meta is not None:
        payload['meta'] = meta
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def fail(code: str, message: str, trace: Optional[str] = None, details=None, retryable: bool = False, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({
            'success': False,
            'trace_id': trace_id(trace),
            'error': {
                'code': code,
                'message': message,
                'details': details or {},
                'retryable': retryable,
            },
        }),
    )


def require_auth(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='auth_required')
    token = authorization.split(' ', 1)[1]
    try:
        return verify_bearer_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail='auth_required') from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail='auth_required') from exc


def ensure_same_user_or_admin(actor: dict, target_id: str):
    if actor['role'] == 'admin':
        return
    if actor['sub'] != target_id:
        raise HTTPException(status_code=403, detail='forbidden')


def body_hash(payload: dict) -> str:
    return 'sha256:' + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def record_idempotency(route: str, key: Optional[str], body_hash: str, response_body: dict):
    if not key:
        return None
    try:
        from services.shared.repositories import IdempotencyRepository
        repo = IdempotencyRepository()
        existing = repo.get(route, key)
        if not existing:
            repo.save(route, key, body_hash, response_body, response_body.get("trace_id") or trace_id())
    except Exception:
        IDEMPOTENCY[(route, key)] = {"body_hash": body_hash, "response": response_body}
        return IDEMPOTENCY[(route, key)]
    return {"body_hash": body_hash, "response": response_body}


def check_idempotency(route: str, key: Optional[str], body_hash: str):
    if not key:
        return None, None
    try:
        from services.shared.repositories import IdempotencyRepository
        repo = IdempotencyRepository()
        record = repo.get(route, key)
        if not record:
            return None, None
        if record["body_hash"] != body_hash:
            return None, "idempotency_conflict"
        return record["response_json"], None
    except Exception:
        record = IDEMPOTENCY.get((route, key))
        if not record:
            return None, None
        if record["body_hash"] != body_hash:
            return None, "idempotency_conflict"
        return record["response"], None


def build_event(
    *,
    event_type: str,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
    trace: str,
    idempotency_key: str | None = None,
) -> dict:
    return {
        'event_type': event_type,
        'trace_id': trace_id(trace),
        'timestamp': utc_now(),
        'actor_id': actor_id,
        'entity': {'entity_type': entity_type, 'entity_id': entity_id},
        'payload': payload,
        'idempotency_key': idempotency_key or f'{event_type}:{entity_id}:{actor_id}',
        'service': service_name(),
    }
