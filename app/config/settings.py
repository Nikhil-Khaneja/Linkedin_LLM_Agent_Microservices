from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Kafka / Redpanda ───────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:19092"
    KAFKA_CONSUMER_GROUP: str = "owner7-analytics"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"

    # ── MongoDB ────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "analytics"

    # ── Redis ──────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300  # 5 minutes default

    # ── App ────────────────────────────────────────────────────────
    ENV: str = "development"
    SERVICE_NAME: str = "owner7-analytics"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
