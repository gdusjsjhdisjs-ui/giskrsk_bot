"""Мои заказы: /myorders для пользователя + отмена заказа."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.config import settings
from app.services.shop_orders import (
    STATUS_AWAITING, STATUS_CLAIMED, STATUS_DELIVERED, STATUS_REJECTED,
    STATUS_LABELS, ShopOrderStore, fmt_amount,
)

router = Router(name="myorders")
_store = ShopOrderStore()

_KIND_ICONS = {
    "shop": "🛎",
    "subscription": "💳",
    "trial": "🎁",
    "clip": "✂️",
}


@router.message(Command("myorders"))
async def cmd_myorders(message: Message) -> None:
    """Показать последние 10 заказов пользователя."""
    user_id = message.from_user.id
    all_orders = _store.list_recent(limit=500)
    my_orders = [o for o in all_orders if o.get("user_id") == user_id][:10]

    if not my_orders:
        await message.answer(
            "📦 <b>Тут пусто</b>\n\n"
            "Вы ещё не сделали ни одной покупки.\n"
            "Смотрите подписки: /tariffs — магазин: /shop"
        )
        return

    lines = ["📋 <b>Ваши покупки (10 последних)</b>\n"]
    cancel_rows = []

    for o in my_orders:
        oid = o["id"]
        kind = o.get("kind", "shop")
        icon = _KIND_ICONS.get(kind, "🛎")
        status_label = STATUS_LABELS.get(o.get("status", ""), o.get("status", "?"))
        amount = fmt_amount(o.get("price", 0), o.get("kopecks", 0))
        date = (o.get("created_at") or "")[:10]
        title = o.get("title") or o.get("item_id", "?")

        lines.append(
            f"{icon} <b>#{oid}</b> {title}\n"
            f"   {status_label} · {amount} · {date}"
        )

        # Кнопка отмены только для ожидающих оплату
        if o.get("status") == STATUS_AWAITING:
            cancel_rows.append([InlineKeyboardButton(
                text=f"❌ Отменить #{oid}",
                callback_data=f"cancel_order:{oid}",
            )])

    kb = InlineKeyboardMarkup(inline_keyboard=cancel_rows) if cancel_rows else None
    await message.answer("\n\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order(callback: CallbackQuery) -> None:
    """Отмена заказа пользователем (только awaiting_payment)."""
    order_id = callback.data.split(":", 1)[1]
    order = _store.get(order_id)

    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    if order.get("user_id") != callback.from_user.id:
        await callback.answer("Чужой заказ.", show_alert=True)
        return
    if order.get("status") != STATUS_AWAITING:
        await callback.answer(
            "Нельзя отменить: оплата уже отправлена или заказ обработан.",
            show_alert=True,
        )
        return

    _store.set_status(order_id, STATUS_REJECTED)
    await callback.message.edit_text(
        f"✅ Заказ #<b>{order_id}</b> отменён.\n"
        f"Если вы всё же оплатили — напишите в поддержку."
    )
    await callback.answer()
