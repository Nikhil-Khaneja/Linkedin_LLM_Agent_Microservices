from services.shared.repositories import AuthRepository as SharedAuthRepository


class AuthRepository(SharedAuthRepository):
    """Thin compatibility wrapper while the rest of the repo is still migrating."""
