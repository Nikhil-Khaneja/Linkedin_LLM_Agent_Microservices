import os


class Settings:
    APP_NAME = os.getenv("APP_NAME", "Owner1 Auth + API Edge")
    APP_ENV = os.getenv("APP_ENV", "dev")
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    MYSQL_URL = os.getenv(
        "MYSQL_URL",
        "mysql+pymysql://root:root@127.0.0.1:3306/auth_access"
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    JWT_ALGORITHM = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    JWT_ISSUER = os.getenv("JWT_ISSUER", "owner1-auth-service")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "linkedin-simulation-services")
    JWKS_KID = os.getenv("JWKS_KID", "owner1-rs256-key-1")

    # Demo RSA PEMs can be injected using env later.
    PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "private_key.pem")
    PUBLIC_KEY_PATH = os.getenv("PUBLIC_KEY_PATH", "public_key.pem")

    LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "10"))

    IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))


settings = Settings()