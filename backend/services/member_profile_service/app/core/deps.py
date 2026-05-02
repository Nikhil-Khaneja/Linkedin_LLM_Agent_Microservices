from functools import lru_cache
from services.member_profile_service.app.repositories.member_repository import MemberProfileRepository
from services.member_profile_service.app.services.member_service import MemberProfileService

@lru_cache
def get_member_repository() -> MemberProfileRepository:
    return MemberProfileRepository()

@lru_cache
def get_member_service() -> MemberProfileService:
    return MemberProfileService(get_member_repository())
