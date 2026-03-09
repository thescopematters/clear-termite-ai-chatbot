"""
cache.py - Redis TTL cache for chat responses.
Persists across restarts and scales across multiple worker instances.
"""

import os
import json
import logging
import hashlib
import redis
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("chatbot_api")

try:
    # Connect to Redis container using URL from .env
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    # Ping to verify connection on startup
    redis_client.ping()
    logger.info("Connected to Redis cache successfully.")
except Exception as e:
    logger.warning(f"Failed to connect to Redis. Responses will not be cached: {e}")
    redis_client = None


class ResponseCache:
    """Redis-backed cache with TTL expiration."""

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds

    def _make_key(self, user_id: int, message: str) -> str:
        """Create a normalized cache key from user_id and message."""
        normalized = message.strip().lower()
        raw = f"chat_cache:{user_id}:{normalized}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, user_id: int, message: str):
        """Return cached response or None if expired/missing/redis down."""
        if not redis_client:
            return None
            
        key = self._make_key(user_id, message)
        try:
            cached_data = redis_client.get(key)
            if cached_data:
                logger.info(f"Redis Cache HIT for {key[:12]}...")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            
        return None

    def set(self, user_id: int, message: str, response: dict):
        """Store a response in Redis with TTL."""
        if not redis_client:
            return
            
        key = self._make_key(user_id, message)
        try:
            # We serialize the Pydantic dict to a JSON string
            json_response = json.dumps(response)
            redis_client.setex(name=key, time=self._ttl, value=json_response)
            logger.info(f"Redis Cache SET for {key[:12]}...")
        except Exception as e:
            logger.error(f"Redis set error: {e}")


# Singleton instance used across the app
response_cache = ResponseCache()

