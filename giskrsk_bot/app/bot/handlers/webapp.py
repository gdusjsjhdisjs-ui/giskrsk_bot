"""Мини-приложение с картой (Telegram Mini App)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app.core.config import settings

router = Router(name="webapp")


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    """Открыть мини-приложение с картой."""
    url = settings.WEBAPP_URL

    if not url:
        await message.answer(
            "\U0001f5fa <b>Карта ГИС Красноярье</b>\n\n"
            "Мини-приложение пока не опубликовано на HTTPS-хостинге.\n\n"
            "\U0001f4bb <b>Локальная версия доступна в браузере:</b>\n"
            "<code>http://localhost:8000/webapp/index.html</code>\n\n"
            "Как опубликовать:\n"
            "1. Выложите папку <code>webapp/</code> на GitHub Pages\n"
            "   (инструкция: <code>webapp/README_MINIAPP.md</code>)\n"
            "2. Впишите адрес в .env:\n"
            "   <code>WEBAPP_URL=https://ваш-адрес/index.html</code>\n"
            "3. Перезапустите бота и наберите /app"
        )
        return

    if not url.startswith("https://"):
        await message.answer(
            "\U0001f5fa <b>Карта ГИС Красноярье</b>\n\n"
            "\u26a0\ufe0f Для Mini App в Telegram требуется HTTPS.\n"
            "Укажите в .env адрес, начинающийся с <code>https://</code>.\n\n"
            "\U0001f4bb Пока карта доступна в браузере:\n"
            f"<code>{url}</code>"
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001f5fa Открыть карту",
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )
    await message.answer(
        "\U0001f5fa <b>Карта ГИС Красноярье</b>\n\n"
        "Зоны ПЗЗ и данные — прямо в Telegram, без логинов и паролей.",
        reply_markup=keyboard,
    )
