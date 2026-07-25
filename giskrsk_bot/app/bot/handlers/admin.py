"""Админ-хендлер: статистика, пользователи, рассылка."""

from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards import admin_keyboard, back_keyboard
from app.bot.keyboards_data import MainMenuAction
from app.bot.filters import IsAdmin
from app.repositories.user_repo import UserRepo
from app.repositories.payment_repo import PaymentRepo
from app.repositories.subscription_repo import SubscriptionRepo
from app.services.profile_store import ProfileStore

router = Router(name="admin")


@router.message(Command("admin"), IsAdmin())
@router.message(F.text == "🔧 Админ-панель", IsAdmin())
async def cmd_admin(message: Message) -> None:
    """Показать админ-панель."""
    await message.answer("🔧 <b>Админ-панель</b>", reply_markup=admin_keyboard())


@router.callback_query(MainMenuAction.filter(F.action == "admin"), IsAdmin())
async def admin_stats(callback: CallbackQuery, **data) -> None:
    """Показать статистику."""
    user_repo: UserRepo | None = data.get("repos", {}).get("user")
    payment_repo: PaymentRepo | None = data.get("repos", {}).get("payment")
    sub_repo: SubscriptionRepo | None = data.get("repos", {}).get("subscription")

    total_users = await user_repo.get_total_count() if user_repo else 0
    active_users = await user_repo.get_active_count() if user_repo else 0
    revenue = await payment_repo.get_total_revenue() if payment_repo else 0
    payments_count = await payment_repo.get_successful_count() if payment_repo else 0
    active_subs = await sub_repo.get_active_count() if sub_repo else 0

    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных: {active_users}\n"
        f"💳 Активных подписок: {active_subs}\n"
        f"💰 Выручка: {revenue:,.0f} ₽\n"
        f"📈 Успешных платежей: {payments_count}",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(MainMenuAction.filter(F.action == "users"), IsAdmin())
async def admin_users(callback: CallbackQuery, **data) -> None:
    """Список пользователей."""
    user_repo: UserRepo | None = data.get("repos", {}).get("user")
    if not user_repo:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    users = await user_repo.get_all_users(limit=20)
    lines = ["👥 <b>Последние 20 пользователей:</b>\n"]
    for u in users:
        blocked = "🚫" if u.is_blocked else "✅"
        lines.append(f"{blocked} {u.telegram_id} | {u.username or '—'} | {u.role}")
        if len(lines) > 25:
            lines.append("...")
            break

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(MainMenuAction.filter(F.action == "broadcast"), IsAdmin())
async def admin_broadcast(callback: CallbackQuery) -> None:
    """Расслыка (заглушка — будет реализована отдельно)."""
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте команду:\n"
        "<code>/promo текст акции</code>\n\n"
        "Сообщение получат все, кто дал согласие на рассылку при регистрации.",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.message(Command("promo"), IsAdmin())
async def cmd_promo(message: Message, bot: Bot) -> None:
    """Рекламная рассылка: /promo текст акции."""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Использование: <code>/promo текст акции</code>\n"
            "Пример: <code>/promo 🔥 Сегодня скидка 20% на тариф Pro!</code>"
        )
        return
    recipients = ProfileStore().consented_ids()
    if not recipients:
        await message.answer("Пока никто не дал согласие на рассылку.")
        return
    import asyncio as _asyncio

    sent = 0
    failed = 0
    for uid in recipients:
        try:
            await bot.send_message(uid, f"📢 {parts[1]}")
            sent += 1
        except Exception:  # noqa: BLE001
            failed += 1
            continue
        await _asyncio.sleep(0.05)  # защита от Telegram 429
    await message.answer(
        f"📢 Рассылка отправлена: {sent} из {len(recipients)}."
        + (f" Не доставлено: {failed}." if failed else "")
    )
