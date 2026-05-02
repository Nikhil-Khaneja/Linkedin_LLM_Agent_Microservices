from functools import lru_cache
from services.ai_orchestrator_service.app.repositories.ai_repository import AIOrchestratorRepository
from services.ai_orchestrator_service.app.services.ai_service import AIOrchestratorService

@lru_cache
def get_ai_repository() -> AIOrchestratorRepository:
    return AIOrchestratorRepository()

@lru_cache
def get_ai_service() -> AIOrchestratorService:
    return AIOrchestratorService(get_ai_repository())
