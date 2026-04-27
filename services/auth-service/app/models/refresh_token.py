from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Integer,    primary_key=True, autoincrement=True)
    user_id    = Column(String(50), nullable=False, index=True)
    token      = Column(Text,       nullable=False)
    is_revoked = Column(Boolean,    default=False, nullable=False)
    created_at = Column(DateTime,   server_default=func.now())
