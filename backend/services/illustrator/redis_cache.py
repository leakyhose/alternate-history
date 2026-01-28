"""Redis cache for portraits."""
import hashlib
import logging
from typing import Optional

import redis

from .config import REDIS_URL, REDIS_PORTRAIT_PREFIX, REDIS_PORTRAIT_TTL_SECONDS

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        logger.info(f"Connecting to Redis at {REDIS_URL}")
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        # Test connection
        _redis_client.ping()
        logger.info("Redis connection established")
    return _redis_client


def make_cache_key(ruler_name: str, nation_name: str, era_context: str) -> str:
    """Create a cache key for a portrait."""
    key_str = f"{ruler_name}|{nation_name}|{era_context}"
    key_hash = hashlib.md5(key_str.encode()).hexdigest()[:16]
    return f"{REDIS_PORTRAIT_PREFIX}{key_hash}"


def get_cached_portrait(ruler_name: str, nation_name: str, era_context: str) -> Optional[str]:
    """Get a cached portrait from Redis."""
    try:
        client = get_redis_client()
        key = make_cache_key(ruler_name, nation_name, era_context)
        portrait = client.get(key)
        if portrait:
            logger.debug(f"Cache hit: {ruler_name}")
        return portrait
    except redis.RedisError as e:
        logger.error(f"Redis get error: {e}")
        return None


def cache_portrait(
    ruler_name: str,
    nation_name: str,
    era_context: str,
    portrait_base64: str,
) -> bool:
    """Store a portrait in Redis with TTL."""
    try:
        client = get_redis_client()
        key = make_cache_key(ruler_name, nation_name, era_context)
        client.setex(key, REDIS_PORTRAIT_TTL_SECONDS, portrait_base64)
        logger.debug(f"Cached portrait: {ruler_name} (TTL={REDIS_PORTRAIT_TTL_SECONDS}s)")
        return True
    except redis.RedisError as e:
        logger.error(f"Redis set error: {e}")
        return False


def store_portrait_for_event(
    game_id: str,
    iteration: int,
    ruler_name: str,
    portrait_base64: str,
) -> str:
    """Store a portrait in Redis and return the key."""
    try:
        client = get_redis_client()
        key = f"portrait:event:{game_id}:{iteration}:{ruler_name}"
        client.setex(key, REDIS_PORTRAIT_TTL_SECONDS, portrait_base64)
        logger.info(f"Stored portrait: {key}")
        return key
    except redis.RedisError as e:
        logger.error(f"Redis store error: {e}")
        return ""


def get_portrait_by_key(key: str) -> Optional[str]:
    """Get a portrait by its Redis key."""
    try:
        client = get_redis_client()
        return client.get(key)
    except redis.RedisError as e:
        logger.error(f"Redis get error: {e}")
        return None


def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
