from upstash_redis.asyncio import Redis
from app.config import settings
import json
import logging

logger = logging.getLogger(__name__)

# Primary Upstash client
redis = Redis(
    url=settings.upstash_redis_rest_url,
    token=settings.upstash_redis_rest_token
)

# Resilient in-memory fallback cache for development/offline mode
_memory_cache: dict[str, dict] = {}

async def get_session_context(session_id: str) -> dict | None:
    try:
        raw = await redis.get(f"session:{session_id}")
        if raw:
            return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.debug(f"Upstash get failed ({e}), checking in-memory cache.")
    return _memory_cache.get(session_id)

async def set_session_context(session_id: str, context: dict) -> None:
    _memory_cache[session_id] = context
    try:
        await redis.set(
            f"session:{session_id}",
            json.dumps(context),
            ex=settings.session_ttl_minutes * 60
        )
    except Exception as e:
        logger.debug(f"Upstash set failed ({e}), stored in in-memory cache.")

async def delete_session(session_id: str) -> None:
    _memory_cache.pop(session_id, None)
    try:
        await redis.delete(f"session:{session_id}")
    except Exception as e:
        logger.debug(f"Upstash delete failed ({e}), removed from in-memory cache.")
