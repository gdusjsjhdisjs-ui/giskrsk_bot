"""Telegram-клиент — обёртка над aiogram Bot для отправки сообщений.

Методы:
  - send_message — отправка текстового сообщения
  - send_document — отправка файла
  - send_notification — отправка с логированием
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)


class TelegramClient:
    """Обёртка над aiogram Bot для типовых операций отправки.

    Принимает экземпляр Bot или None (тогда получает из настроек).

    Все публичные методы — async.
    """

    def __init__(self, bot: Bot | None = None) -> None:
        if bot is not None:
            self._bot: Bot = bot
        else:
            # Ленивая инициализация — получаем Bot из настроек
            from app.core.config import settings

            from aiogram.client.default import DefaultBotProperties

            self._bot = Bot(
                token=settings.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode="HTML"),
            )

        logger.info("TelegramClient инициализирован")

    @property
    def bot(self) -> Bot:
        """Экземпляр aiogram Bot."""
        return self._bot

    # ─── Публичные методы ──────────────────────────────────────────────

    async def send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs: Any,
    ) -> Message:
        """Отправить текстовое сообщение.

        Args:
            chat_id: ID чата / пользователя.
            text: Текст сообщения.
            **kwargs: Дополнительные аргументы aiogram Bot.send_message
                      (parse_mode, reply_markup, disable_web_page_preview и т.д.).

        Returns:
            Объект отправленного Message.
        """
        return await self._bot.send_message(chat_id=chat_id, text=text, **kwargs)

    async def send_document(
        self,
        chat_id: int,
        document: Any,
        filename: str = "",
        caption: str = "",
        **kwargs: Any,
    ) -> Message:
        """Отправить файл (документ).

        Args:
            chat_id: ID чата / пользователя.
            document: Файл (путь, BytesIO, InputFile и т.д.).
            filename: Имя файла (для отображения в Telegram).
            caption: Подпись к файлу.
            **kwargs: Дополнительные аргументы aiogram Bot.send_document.

        Returns:
            Объект отправленного Message.
        """
        # Если передан filename, используем InputFile
        if filename and not getattr(document, "filename", None):
            from aiogram.types import FSInputFile

            if isinstance(document, str):
                document = FSInputFile(document, filename=filename)

        return await self._bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            **kwargs,
        )

    async def send_notification(
        self,
        telegram_id: int,
        text: str,
    ) -> bool:
        """Отправить уведомление пользователю с логированием.

        Отличается от send_message тем, что гарантированно логирует
        успех или неудачу.

        Args:
            telegram_id: ID пользователя в Telegram.
            text: Текст уведомления.

        Returns:
            True если отправлено успешно, False при ошибке.
        """
        try:
            await self._bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info("Уведомление отправлено пользователю %s", telegram_id)
            return True
        except Exception as exc:
            logger.error(
                "Ошибка отправки уведомления %s: %s",
                telegram_id,
                exc,
            )
            return False
