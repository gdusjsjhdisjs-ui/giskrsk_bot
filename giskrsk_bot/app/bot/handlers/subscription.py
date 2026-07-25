"""Хендлер управления подпиской."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards import subscription_keyboard, back_keyboard
from app.bot.keyboards_data import SubscriptionAction
from app.services.subscription_service import SubscriptionService

router = Router(name="subscription")


def get_sub_service(data: dict) -> SubscriptionService | None:
    return data.get("services", {}).get("subscription")


@router.message(Command("subscribe"))
@router.message(F.text == "📋 Моя подписка")
async def cmd_my_subscription(message: Message, **data) -> None:
    """Показать информацию о подписке."""
    sub_service = get_sub_service(data)
    if not sub_service:
        await message.answer("❌ Сервис недоступен.")
        return

    sub = await sub_service.get_active(message.from_user.id)
    if sub:
        await message.answer(
            f"✅ <b>Подписка активна</b>\n\n"
            f"📦 Тариф: {sub['plan_code']}\n"
            f"📅 Действует до: {sub['expires_at']}\n"
            f"⏳ Осталось дней: {sub['days_left']}",
            reply_markup=subscription_keyboard("active"),
        )
    else:
        role = await sub_service.get_role(message.from_user.id)
        limits = {"free": 3, "basic": 30, "pro": 100}
        limit = limits.get(role, 3)
        await message.answer(
            f"🆓 <b>У вас нет активной подписки</b>\n\n"
            f"Текущий лимит: {limit} проверок в день\n\n"
            f"💳 Чтобы получить больше — оформите подписку: /tariffs",
            reply_markup=subscription_keyboard("none"),
        )


@router.callback_query(SubscriptionAction.filter(F.action == "status"))
async def sub_status(callback: CallbackQuery, **data) -> None:
    """Проверить статус подписки."""
    sub_service = get_sub_service(data)
    if not sub_service:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    sub = await sub_service.get_active(callback.from_user.id)
    if sub:
        await callback.message.edit_text(
            f"✅ <b>Подписка активна</b>\n\n"
            f"📦 Тариф: {sub['plan_code']}\n"
            f"⏳ Осталось дней: {sub['days_left']}",
            reply_markup=subscription_keyboard("active"),
        )
    else:
        await callback.message.edit_text(
            "❌ Нет активной подписки.",
            reply_markup=subscription_keyboard("none"),
        )
    await callback.answer()


@router.callback_query(SubscriptionAction.filter(F.action == "extend"))
async def sub_extend(callback: CallbackQuery, **data) -> None:
    """Продлить подписку."""
    await callback.message.edit_text(
        "💳 Выберите тариф для продления:",
        reply_markup=None,
    )
    await callback.message.answer("👉 /tariffs — посмотреть тарифы")
    await callback.answer()


@router.callback_query(SubscriptionAction.filter(F.action == "cancel"))
async def sub_cancel(callback: CallbackQuery, **data) -> None:
    """Отменить подписку."""
    sub_service = get_sub_service(data)
    if not sub_service:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    success = await sub_service.cancel(callback.from_user.id)
    if success:
        await callback.message.edit_text("✅ Подписка отменена.", reply_markup=back_keyboard("main_menu"))
    else:
        await callback.message.edit_text("❌ Активная подписка не найдена.")
    await callback.answer()
