"""Хендлер профиля пользователя."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards import back_keyboard
from app.bot.keyboards_data import ProfileAction
from app.repositories.user_repo import UserRepo
from app.services.subscription_service import SubscriptionService

router = Router(name="profile")


@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message, **data) -> None:
    """Показать профиль пользователя."""
    user_repo: UserRepo | None = data.get("repos", {}).get("user")
    sub_service: SubscriptionService | None = data.get("services", {}).get("subscription")

    if not user_repo:
        await message.answer("❌ Сервис недоступен.")
        return

    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return

    # Подписка
    sub_text = "Нет активной подписки"
    if sub_service:
        sub = await sub_service.get_active(message.from_user.id)
        if sub:
            sub_text = f"✅ {sub['plan_code']} (до {sub['expires_at'][:10]}, осталось {sub['days_left']} дн.)"

    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: {user.telegram_id}\n"
        f"📛 Имя: {user.full_name or '—'}\n"
        f"🔖 Роль: {user.role}\n"
        f"📊 Запросов сегодня: {user.daily_requests_used}\n"
        f"💳 Подписка: {sub_text}\n"
        f"📅 Зарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}",
        reply_markup=back_keyboard("main_menu"),
    )


@router.callback_query(ProfileAction.filter(F.action == "show"))
async def profile_show(callback: CallbackQuery, **data) -> None:
    """Показать профиль (из callback)."""
    await cmd_profile(callback.message, **data)
    await callback.answer()
