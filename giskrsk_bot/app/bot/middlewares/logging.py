import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Логирует все входящие сообщения и callback_query.

    Формат:
      [user_id @username] текст[:100]

    Замеряет время выполнения хендлера и логирует его.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_id = user.id if user else 0
        username = f"@{user.username}" if user and user.username else "—"

        # Извлекаем текст/данные события
        if isinstance(event, Message):
            payload = (event.text or event.caption or "[media]")[:100]
        elif isinstance(event, CallbackQuery):
            payload = f"[callback] {event.data}"[:100]
        else:
            payload = f"[{type(event).__name__}]"

        logger.info("[%s %s] %s", user_id, username, payload)

        start = time.monotonic()
        try:
            result = await handler(event, data)
        except Exception:
            elapsed = time.monotonic() - start
            logger.error(
                "[%s %s] ERROR after %.3fs | %s",
                user_id,
                username,
                elapsed,
                payload,
            )
            raise

        elapsed = time.monotonic() - start
        logger.info(
            "[%s %s] OK %.3fs | %s",
            user_id,
            username,
            elapsed,
            payload,
        )
        return result
