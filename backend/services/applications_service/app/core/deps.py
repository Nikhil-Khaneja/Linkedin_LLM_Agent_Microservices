from functools import lru_cache
from services.applications_service.app.repositories.application_repository import ApplicationsRepository
from services.applications_service.app.services.applications_service import ApplicationsService

@lru_cache
def get_applications_repository() -> ApplicationsRepository:
    return ApplicationsRepository()

@lru_cache
def get_applications_service() -> ApplicationsService:
    return ApplicationsService(get_applications_repository())
