from functools import lru_cache
from services.jobs_service.app.repositories.job_repository import JobsRepository
from services.jobs_service.app.services.jobs_service import JobsService

@lru_cache
def get_jobs_repository() -> JobsRepository:
    return JobsRepository()

@lru_cache
def get_jobs_service() -> JobsService:
    return JobsService(get_jobs_repository())
