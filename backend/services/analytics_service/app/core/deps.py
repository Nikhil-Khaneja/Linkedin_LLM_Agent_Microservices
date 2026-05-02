from functools import lru_cache
from services.analytics_service.app.repositories.analytics_repository import AnalyticsRepository, AnalyticsRollupsRepository
from services.analytics_service.app.services.analytics_service import AnalyticsService

@lru_cache
def get_analytics_repository() -> AnalyticsRepository:
    return AnalyticsRepository()

@lru_cache
def get_analytics_rollups_repository() -> AnalyticsRollupsRepository:
    return AnalyticsRollupsRepository()

@lru_cache
def get_analytics_service() -> AnalyticsService:
    return AnalyticsService(get_analytics_repository(), get_analytics_rollups_repository())
