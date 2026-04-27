from sqlalchemy.orm import Session

from app.models.idempotency_request import IdempotencyRequest


def get_idempotency_record(db: Session, idem_key: str) -> IdempotencyRequest | None:
    return db.query(IdempotencyRequest).filter(IdempotencyRequest.idem_key == idem_key).first()


def create_idempotency_record(
    db: Session, idem_key: str, request_hash: str, method: str, path: str
) -> IdempotencyRequest:
    row = IdempotencyRequest(
        idem_key=idem_key,
        request_hash=request_hash,
        method=method,
        path=path,
        response_body=None,
        status_code=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_idempotency_response(
    db: Session, row: IdempotencyRequest, status_code: int, response_body: str
) -> None:
    row.status_code = status_code
    row.response_body = response_body
    db.commit()