"""Хендлер помощи."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards import back_keyboard

router = Router(name="help")


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message) -> None:
    """Показать справку."""
    await message.answer(
        "ℹ️ <b>ГИС Красноярье — Помощь</b>\n\n"
        "<b>Основные команды:</b>\n\n"
        "/start — главное меню\n"
        "/parcel — проверка участка по кадастровому номеру\n"
        "/tariffs — тарифы и оформление подписки\n"
        "/subscribe — состояние текущей подписки\n"
        "/tracking — отслеживание участков\n"
        "/batch — пакетная проверка (CSV)\n"
        "/shop — магазин геоданных (ПЗЗ, QGIS)\n"
        "/myorders — история ваших заказов\n"
        "/torgi — публичные торги по земле\n"
        "/app — карта и клип по области\n"
        "/profile — профиль\n"
        "/help — эта справка\n\n"
        "<b>Как пользоваться:</b>\n\n"
        "1️⃣ <b>Проверить участок</b> — введите кадастровый номер.\n"
        "   Получите зону ПЗЗ, ВРИ, стоимость.\n\n"
        "2️⃣ <b>Геопозиция</b> — отправьте точку на карте.\n"
        "   Узнайте, в какой зоне находится участок.\n\n"
        "3️⃣ <b>Магазин</b> — купите готовые геоданные (/shop).\n"
        "   Или выберите нужный район на карте (/app) — клип.\n\n"
        "4️⃣ <b>Пакетная проверка</b> — CSV со списком номеров,\n"
        "   получите Excel с результатами.\n\n"
        "5️⃣ <b>Торги</b> — участки на аукцион из Росимущества.\n\n"
        "❓ Вопросы и поддержка: /help",
        reply_markup=back_keyboard("main_menu"),
    )
