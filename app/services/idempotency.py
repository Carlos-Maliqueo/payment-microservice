import json
from typing import Optional, Any
import structlog

logger = structlog.get_logger()


class IdempotencyService:
    def __init__(self):
        self._redis_client = None
        self._redis_available = None

    async def _get_client(self):
        if self._redis_available is False:
            return None
        try:
            import redis.asyncio as redis
            from app.core.config import settings
            if self._redis_client is None:
                self._redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self._redis_client.ping()
            self._redis_available = True
            return self._redis_client
        except Exception:
            self._redis_available = False
            logger.warning("redis_unavailable_idempotency_disabled")
            return None

    def _key(self, idempotency_key: str) -> str:
        return f"idempotency:{idempotency_key}"

    def _lock_key(self, idempotency_key: str) -> str:
        return f"idempotency:lock:{idempotency_key}"

    async def get_cached_response(self, idempotency_key: str) -> Optional[dict]:
        client = await self._get_client()
        if not client:
            return None
        try:
            cached = await client.get(self._key(idempotency_key))
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None

    async def acquire_lock(self, idempotency_key: str) -> bool:
        client = await self._get_client()
        if not client:
            return True  # Sin Redis, siempre permitir
        try:
            acquired = await client.set(self._lock_key(idempotency_key), "locked", nx=True, ex=30)
            return acquired is not None
        except Exception:
            return True

    async def save_response(self, idempotency_key: str, response: Any) -> None:
        client = await self._get_client()
        if not client:
            return
        try:
            from app.core.config import settings
            await client.setex(self._key(idempotency_key), settings.IDEMPOTENCY_TTL_SECONDS, json.dumps(response, default=str))
        except Exception:
            pass

    async def release_lock(self, idempotency_key: str) -> None:
        client = await self._get_client()
        if not client:
            return
        try:
            await client.delete(self._lock_key(idempotency_key))
        except Exception:
            pass


idempotency_service = IdempotencyService()