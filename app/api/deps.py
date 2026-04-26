from typing import Generator

from fastapi import Header, Request
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown-request-id")