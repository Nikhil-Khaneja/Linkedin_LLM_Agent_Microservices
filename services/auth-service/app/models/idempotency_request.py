from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class IdempotencyRequest(Base):
    __tablename__ = "idempotency_requests"

    id = Column(Integer, primary_key=True, index=True)
    idem_key = Column(String(255), unique=True, nullable=False, index=True)
    request_hash = Column(String(255), nullable=False)
    method = Column(String(20), nullable=False)
    path = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())