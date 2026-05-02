from functools import lru_cache
from services.recruiter_company_service.app.repositories.recruiter_repository import RecruiterCompanyRepository
from services.recruiter_company_service.app.services.recruiter_service import RecruiterCompanyService

@lru_cache
def get_recruiter_repository() -> RecruiterCompanyRepository:
    return RecruiterCompanyRepository()

@lru_cache
def get_recruiter_service() -> RecruiterCompanyService:
    return RecruiterCompanyService(get_recruiter_repository())
