"""
Configuration settings for Job Service
Uses pydantic-settings for environment variable management
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Service info
    service_name: str = "job-service"
    service_port: int = 3004
    debug: bool = False

    # Database (MySQL)
    database_host: str = "localhost"
    database_port: int = 3306
    database_user: str = "root"
    database_password: str = "password"
    database_name: str = "job_core"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Cache TTL (seconds)
    cache_ttl_job_detail: int = 300  # 5 minutes
    cache_ttl_job_search: int = 120  # 2 minutes
    cache_ttl_recruiter_jobs: int = 180  # 3 minutes

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_client_id: str = "job-service"

    # JWT/Auth
    jwks_url: str = "http://localhost:8001/api/v1/.well-known/jwks.json"
    jwt_algorithm: str = "RS256"

    @property
    def database_url(self) -> str:
        """Build MySQL connection URL"""
        return f"mysql+mysqlconnector://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
