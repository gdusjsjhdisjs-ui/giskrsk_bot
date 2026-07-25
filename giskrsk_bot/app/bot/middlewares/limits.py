"""Мидлвар: дневной лимит запросов.

Лимиты по планам:
  free : 3  запроса в день
  basic: 30 запросов в день
  pro  : 100 запросов в день
  admin: без лимита

Счётчик: внутрипроцессный dict (user_id, date_str) -> int.
На VPS с Redis замените _mem_increment/_mem_check на
вызовы Redis (ключ cache.check_and_increment_daily).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.config import settings

# Дневные лимиты по планам
_DAILY_LIMITS: dict[str, int] = {
    "free": settings.DAILY_LIMIT_FREE,
    "basic": settings.DAILY_LIMIT_BASIC,
    "pro": settings.DAILY_LIMIT_PRO,
}

# Внутрипроцессный счётчик: (telegram_id, "2026-07-20") -> количество запросов
_counters: dict[tuple[int, str], int] = defaultdict(int)
_ctr_lock = asyncio.Lock()


async def _mem_increment(user_id: int) -> int:
    """Увеличить счётчик и вернуть текущее значение."""
    key = (user_id, date.today().isoformat())
    async with _ctr_lock:
        _counters[key] += 1
        return _counters[key]


class DailyLimitMiddleware(BaseMiddleware):
    """Проверяет дневной лимит запросов до вызова хендлера."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        # Администраторы пропускаются без лимита
        if user.id in settings.ADMIN_IDS:
            return await handler(event, data)

        # Попытка узнать план через Redis/сервис подписок
        sub_service = (data.get("services") or {}).get("subscription")
        user_plan = "free"
        if sub_service:
            try:
                user_plan = await sub_service.get_role(user.id)
            except Exception:  # noqa: BLE001
                pass

        daily_limit = _DAILY_LIMITS.get(user_plan, settings.DAILY_LIMIT_FREE)

        # Попытка использовать Redis, если доступен
        cache = (data.get("services") or {}).get("redis")
        if cache:
            try:
                allowed, current = await cache.check_and_increment_daily(user.id, daily_limit)
                if not allowed:
                    await _send_limit_msg(event, user_plan, daily_limit)
                    return
                return await handler(event, data)
            except Exception:  # noqa: BLE001
                pass  # Redis недоступен — фоллбэк на in-memory

        # In-memory фоллбэк (один процесс, polling)
        current = await _mem_increment(user.id)
        if current > daily_limit:
            await _send_limit_msg(event, user_plan, daily_limit)
            return

        return await handler(event, data)


async def _send_limit_msg(
    event: TelegramObject, user_plan: str, daily_limit: int
) -> None:
    text = (
        "\U0001f6ab <b>Дневной лимит исчерпан.</b>\n\n"
        f"Ваш тариф: <b>{user_plan.capitalize()}</b> — до {daily_limit} запросов в день.\n\n"
        "Поднять лимит: /tariffs"
    )
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.answer(
            f"Дневной лимит исчерпан ({daily_limit} зап.). Поднять: /tariffs",
            show_alert=True,
        )
