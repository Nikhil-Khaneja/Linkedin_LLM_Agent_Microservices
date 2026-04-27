"""
MongoDB + Redis connection lifecycle, attached to FastAPI startup/shutdown.
"""
import motor.motor_asyncio
import redis.asyncio as aioredis
import logging
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# ── Module-level singletons ───────────────────────────────────────
_mongo_client: motor.motor_asyncio.AsyncIOMotorClient = None
_mongo_db = None
_redis_client: aioredis.Redis = None


async def connect_mongo():
    global _mongo_client, _mongo_db
    settings = get_settings()
    _mongo_client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)
    _mongo_db = _mongo_client[settings.MONGODB_DB]
    # Create indexes
    await _mongo_db.events_raw.create_index([("event_type", 1), ("timestamp", 1)])
    await _mongo_db.events_raw.create_index([("idempotency_key", 1)], unique=True, sparse=True)
    await _mongo_db.events_raw.create_index([("entity.entity_id", 1)])
    await _mongo_db.recruiter_dash_rollups.create_index([("job_id", 1), ("date", 1)])
    await _mongo_db.member_dash_rollups.create_index([("member_id", 1), ("date", 1)])
    await _mongo_db.benchmark_runs.create_index([("scenario", 1), ("created_at", -1)])
    logger.info("MongoDB connected and indexes ensured")


async def connect_redis():
    global _redis_client
    settings = get_settings()
    _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await _redis_client.ping()
    logger.info("Redis connected")


async def close_connections():
    global _mongo_client, _redis_client
    if _mongo_client:
        _mongo_client.close()
    if _redis_client:
        await _redis_client.close()
    logger.info("Database connections closed")


def get_db():
    return _mongo_db


def get_redis():
    return _redis_client
