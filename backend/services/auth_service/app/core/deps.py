from functools import lru_cache

from services.auth_service.app.repositories.auth_repository import AuthRepository
from services.auth_service.app.services.auth_service import AuthService


@lru_cache
def get_auth_repository() -> AuthRepository:
    return AuthRepository()


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(get_auth_repository())
