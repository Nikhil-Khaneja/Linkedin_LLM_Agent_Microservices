"""
redis_client.py — Shared Redis connection for Owner 5.
Used only for fast duplicate-application / idempotency checks.
"""

import logging
import redis
from app.config import REDIS_HOST, REDIS_PORT

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis():
    """Return a Redis connection, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            logger.info("Redis connected at %s:%s", REDIS_HOST, REDIS_PORT)
        except Exception as exc:
            logger.warning("Redis unavailable: %s — continuing without cache", exc)
            _redis_client = None
    return _redis_client


def make_idem_key(member_id: str, job_id: str) -> str:
    """Canonical Redis key for duplicate-apply prevention."""
    return f"apply:idem:{member_id}:{job_id}"
