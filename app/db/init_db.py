from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.idempotency_request import IdempotencyRequest


def init_db() -> None:
    Base.metadata.create_all(bind=engine)