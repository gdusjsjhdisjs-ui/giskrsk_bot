"""Redis-кэш с автоматическим фолбэком в память процесса.

Если Redis недоступен (например, локальный запуск с USE_SQLITE=true
без Docker), кэш прозрачно переключается на встроенное хранилище
в памяти: бот продолжает работать, лимиты и кэш действуют до
перезапуска процесса. Для продакшена Redis по-прежнему рекомендуется
(в Docker поднимается автоматически из docker-compose.yml).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_PARCEL_PREFIX = "parcel:"
_DAILY_PREFIX = "daily:"
_VERIFY_PREFIX = "verify:"
_TEMP_PREFIX = "temp:"
_PARCEL_TTL = 3600
_TEMP_TTL = 300
_VERIFY_TTL = 30


def _seconds_to_midnight() -> int:
    now = datetime.now()
    midnight = datetime(now.year, now.month, now.day, 23, 59, 59)
    return max(int((midnight - now).total_seconds()), 3600)


class _MemoryStore:
    """Простое хранилище ключ-значение с TTL в памяти процесса."""

    def __init__(self) -> None:
        # key -> (value, expires_at_monotonic | None)
        self._data: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at < time.monotonic():
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        expires_at = time.monotonic() + ttl if ttl else None
        self._data[key] = (value, expires_at)

    def set_nx(self, key: str, value: str, ttl: int | None = None) -> bool:
        if self.get(key) is not None:
            return False
        self.set(key, value, ttl)
        return True

    def incr(self, key: str, ttl: int | None = None) -> int:
        current = self.get(key)
        new_value = (int(current) if current else 0) + 1
        entry = self._data.get(key)
        expires_at = entry[1] if entry else (
            time.monotonic() + ttl if ttl else None
        )
        self._data[key] = (str(new_value), expires_at)
        return new_value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class RedisCache:
    """Redis-кэш; при недоступности Redis — фолбэк в память процесса."""

    def __init__(self) -> None:
        self._mem = _MemoryStore()
        self._fallback = False
        try:
            self._redis: aioredis.Redis | None = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=3,
            )
        except Exception as exc:  # noqa: BLE001
            self._redis = None
            self._enable_fallback(exc)

    # ---------- внутреннее ----------

    def _enable_fallback(self, exc: Exception | None = None) -> None:
        if not self._fallback:
            self._fallback = True
            logger.warning(
                "Redis недоступен (%s) — переключаюсь на кэш в памяти процесса. "
                "Бот работает штатно; для продакшена запустите Redis "
                "(docker run -d -p 6379:6379 redis:7-alpine).",
                exc,
            )

    async def _get(self, key: str) -> str | None:
        if not self._fallback and self._redis is not None:
            try:
                return await self._redis.get(key)
            except Exception as exc:  # noqa: BLE001
                self._enable_fallback(exc)
        return self._mem.get(key)

    async def _setex(self, key: str, ttl: int, value: str) -> None:
        if not self._fallback and self._redis is not None:
            try:
                await self._redis.setex(key, ttl, value)
                return
            except Exception as exc:  # noqa: BLE001
                self._enable_fallback(exc)
        self._mem.set(key, value, ttl)

    async def _delete(self, key: str) -> None:
        if not self._fallback and self._redis is not None:
            try:
                await self._redis.delete(key)
                return
            except Exception as exc:  # noqa: BLE001
                self._enable_fallback(exc)
        self._mem.delete(key)

    async def _incr_with_ttl(self, key: str, ttl: int) -> int:
        if not self._fallback and self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.ttl(key)
                results = await pipe.execute()
                used = int(results[0])
                if results[1] < 0:
                    await self._redis.expire(key, ttl)
                return used
            except Exception as exc:  # noqa: BLE001
                self._enable_fallback(exc)
        return self._mem.incr(key, ttl)

    # ---------- кэш участков ----------

    async def get_parcel_cache(self, cadnum: str) -> dict[str, Any] | None:
        data = await self._get(f"{_PARCEL_PREFIX}{cadnum}")
        return json.loads(data) if data else None

    async def set_parcel_cache(self, cadnum: str, data: dict, ttl: int = _PARCEL_TTL) -> None:
        await self._setex(f"{_PARCEL_PREFIX}{cadnum}", ttl, json.dumps(data, default=str))

    async def invalidate_parcel_cache(self, cadnum: str) -> None:
        await self._delete(f"{_PARCEL_PREFIX}{cadnum}")

    # ---------- дневные лимиты ----------

    async def check_and_increment_daily(self, telegram_id: int, limit: int) -> tuple[bool, int]:
        """Проверка лимита + инкремент одним вызовом."""
        key = f"{_DAILY_PREFIX}{telegram_id}:{date.today().isoformat()}"
        used = await self._incr_with_ttl(key, _seconds_to_midnight())
        return used <= limit, used

    async def check_daily_limit(self, telegram_id: int, limit: int) -> tuple[bool, int]:
        key = f"{_DAILY_PREFIX}{telegram_id}:{date.today().isoformat()}"
        used = await self._get(key)
        if used is None:
            return True, 0
        return int(used) < limit, int(used)

    async def increment_daily_counter(self, telegram_id: int) -> int:
        key = f"{_DAILY_PREFIX}{telegram_id}:{date.today().isoformat()}"
        return await self._incr_with_ttl(key, _seconds_to_midnight())

    # ---------- блокировки ----------

    async def acquire_verify_lock(self, telegram_id: int, timeout: int = _VERIFY_TTL) -> bool:
        key = f"{_VERIFY_PREFIX}{telegram_id}"
        if not self._fallback and self._redis is not None:
            try:
                return bool(await self._redis.set(key, "1", nx=True, ex=timeout))
            except Exception as exc:  # noqa: BLE001
                self._enable_fallback(exc)
        return self._mem.set_nx(key, "1", timeout)

    async def release_verify_lock(self, telegram_id: int) -> None:
        await self._delete(f"{_VERIFY_PREFIX}{telegram_id}")

    # ---------- временные данные ----------

    async def set_temp_data(self, key: str, data: dict, ttl: int = _TEMP_TTL) -> None:
        await self._setex(f"{_TEMP_PREFIX}{key}", ttl, json.dumps(data, default=str))

    async def get_temp_data(self, key: str) -> dict[str, Any] | None:
        data = await self._get(f"{_TEMP_PREFIX}{key}")
        return json.loads(data) if data else None

    async def delete_temp_data(self, key: str) -> None:
        await self._delete(f"{_TEMP_PREFIX}{key}")

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:  # noqa: BLE001
                pass
