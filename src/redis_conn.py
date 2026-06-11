import asyncio
import json
import logging

import redis.asyncio as redis
from fastapi import HTTPException, status

from src.config import settings

log = logging.getLogger("redis")


class RedisClient:
    def __init__(self):
        self.redis = None

    async def connect(self):
        if self.redis is not None:
            return

        for attempt in range(3):
            try:
                r = await redis.from_url(settings.REDIS_URL, decode_responses=True)
                await r.ping()
                self.redis = r
                log.info("Redis connected")
                return
            except Exception as e:
                log.warning(f"Redis attempt {attempt + 1}/3: {e}")
                await asyncio.sleep(2)

        raise RuntimeError("Redis connection failed after 3 attempts")

    async def close(self):
        if self.redis:
            await self.redis.aclose()
            self.redis = None

    async def get_redis(self):
        if self.redis is None:
            log.warning("Redis не подключён")
            await self.connect()
        return self.redis

    async def load(self, key: str, data: dict | str, ttl: int):
        try:
            r = await self.get_redis()
            value = json.dumps(data) if isinstance(data, (dict, list)) else data
            await r.setex(key, ttl, value)
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Redis load error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"msg": "Кэш недоступен"},
            )

    async def get(self, key: str) -> dict | str | None:
        try:
            r = await self.get_redis()
            data = await r.get(key)
            if data is None:
                return None
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Redis get error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"msg": "Кэш недоступен"},
            )

    async def blacklist_token(self, jti: str, ttl: int):
        r = await self.get_redis()
        await r.set(f"blacklist:{jti}", "1", ex=ttl)
        log.info(f"blacklisted: jti={jti}, ttl={ttl}s")

    async def is_blacklisted(self, jti: str) -> bool:
        r = await self.get_redis()
        return await r.exists(f"blacklist:{jti}") == 1


redis_client = RedisClient()