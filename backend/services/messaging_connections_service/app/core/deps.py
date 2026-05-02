from functools import lru_cache
from services.messaging_connections_service.app.repositories.messaging_repository import MessagingConnectionsRepository
from services.messaging_connections_service.app.services.messaging_service import MessagingConnectionsService

@lru_cache
def get_messaging_repository() -> MessagingConnectionsRepository:
    return MessagingConnectionsRepository()

@lru_cache
def get_messaging_service() -> MessagingConnectionsService:
    return MessagingConnectionsService(get_messaging_repository())
