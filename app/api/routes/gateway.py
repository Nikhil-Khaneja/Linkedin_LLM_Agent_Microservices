from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.idempotency_request import IdempotencyRequest
from app.schemas.auth import IdempotencyCheckRequest, IdempotencyCheckResponse

router = APIRouter(prefix="/gateway", tags=["gateway"])


@router.post("/idempotency/check", response_model=IdempotencyCheckResponse)
def check_idempotency(payload: IdempotencyCheckRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(IdempotencyRequest)
        .filter(IdempotencyRequest.idem_key == payload.idempotency_key)
        .first()
    )

    if existing:
        if existing.request_hash == payload.request_hash:
            return IdempotencyCheckResponse(
                safe_to_process=False,
                message="Duplicate request detected",
                cached_response=existing.response_body,
            )
        return IdempotencyCheckResponse(
            safe_to_process=False,
            message="Idempotency key reused with different payload",
            cached_response=None,
        )

    row = IdempotencyRequest(
        idem_key=payload.idempotency_key,
        request_hash=payload.request_hash,
        method="POST",
        path="/gateway/idempotency/check",
    )
    db.add(row)
    db.commit()

    return IdempotencyCheckResponse(
        safe_to_process=True,
        message="Safe to process",
        cached_response=None,
    )