"""
Redis configuration and connection management
"""
import redis.asyncio as redis
import json
import hashlib
import logging
from typing import Optional, Any

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Redis client instance
redis_client: Optional[redis.Redis] = None


async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None,
            decode_responses=True
        )
        # Test connection
        await redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        # Don't raise - Redis failure shouldn't stop the service
        redis_client = None


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


def get_redis() -> Optional[redis.Redis]:
    """Get Redis client instance"""
    return redis_client


class CacheService:
    """Service for Redis caching operations"""

    def __init__(self):
        self.client = redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.client:
            return False
        try:
            await self.client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.client:
            return 0
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self.client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning(f"Cache delete pattern failed for {pattern}: {e}")
            return 0

    @staticmethod
    def generate_search_key(filters: dict, pagination: dict) -> str:
        """Generate cache key for search filters"""
        # Combine filters and pagination
        cache_data = {
            "filters": filters,
            "pagination": pagination
        }
        # Create deterministic hash
        data_str = json.dumps(cache_data, sort_keys=True)
        hash_value = hashlib.md5(data_str.encode()).hexdigest()[:12]
        return f"jobs:search:{hash_value}"

    async def invalidate_job(self, job_id: str):
        """Invalidate all caches related to a job"""
        await self.delete(f"job:detail:{job_id}")
        # Invalidate search caches
        await self.delete_pattern("jobs:search:*")

    async def invalidate_recruiter_jobs(self, recruiter_id: str):
        """Invalidate recruiter's job list cache"""
        await self.delete(f"jobs:recruiter:{recruiter_id}")
        await self.delete_pattern("jobs:search:*")


# Global cache service instance
cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get cache service instance"""
    global cache_service
    if cache_service is None:
        cache_service = CacheService()
    return cache_service
