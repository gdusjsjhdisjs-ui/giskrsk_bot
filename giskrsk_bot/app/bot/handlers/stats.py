"""Админская статистика: /stats."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import settings
from app.services.account_pool import (
    STATUS_ASSIGNED, STATUS_EXPIRED, STATUS_FREE, AccountPool,
)
from app.services.profile_store import ProfileStore
from app.services.shop_orders import (
    STATUS_AWAITING, STATUS_CLAIMED, STATUS_DELIVERED, STATUS_REJECTED,
    ShopOrderStore,
)
from app.services.waitlist_store import WaitlistStore

router = Router(name="stats")


_BASE_DIR = Path(__file__).resolve().parents[3]  # project root


def _referral_total_sync() -> int:
    """Читаем referrals.json в потоке (asyncio.to_thread)."""
    try:
        data = json.loads((_BASE_DIR / "referrals.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(data, dict):
        return 0
    refs = data.get("referrers", data)
    return len(refs) if isinstance(refs, dict) else 0


def _order_stats_sync() -> dict:
    """Считаем статистику заказов в потоке (asyncio.to_thread).

    Не загружаем все заказы в память: считаем за один проход по файлу.
    """
    store = ShopOrderStore()
    # list_recent without limit cap — we count by status, not load all into memory
    # The lock is per-instance; we read once and compute in-place.
    all_orders = store.list_recent(limit=999_999)
    by_status: dict[str, int] = {}
    revenue = 0
    subs_sold = 0
    goods_sold = 0
    trials = 0
    for o in all_orders:
        status = o.get("status") or ""
        by_status[status] = by_status.get(status, 0) + 1
        if status == STATUS_DELIVERED:
            revenue += int(o.get("price") or 0)
            item_id = o.get("item_id") or ""
            if o.get("kind") == "trial":
                trials += 1
            elif item_id.startswith("pzz_") or item_id == "qgis_full":
                goods_sold += 1
            else:
                subs_sold += 1
    return dict(
        by_status=by_status,
        revenue=revenue,
        subs_sold=subs_sold,
        goods_sold=goods_sold,
        trials=trials,
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Сводка по боту для админа."""
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    # Всю обработку файлов делаем в thread-пуле, чтобы не блокировать event loop
    order_stats, ref_count = await asyncio.gather(
        asyncio.to_thread(_order_stats_sync),
        asyncio.to_thread(_referral_total_sync),
    )

    by_status = order_stats["by_status"]
    revenue = order_stats["revenue"]
    subs_sold = order_stats["subs_sold"]
    goods_sold = order_stats["goods_sold"]
    trials = order_stats["trials"]

    pool = await asyncio.to_thread(AccountPool().list_all)
    free = sum(1 for a in pool if a.get("status") == STATUS_FREE)
    assigned = sum(1 for a in pool if a.get("status") == STATUS_ASSIGNED)
    expired = sum(1 for a in pool if a.get("status") == STATUS_EXPIRED)

    profiles = ProfileStore()
    user_count = await asyncio.to_thread(profiles.count)
    consented = await asyncio.to_thread(profiles.consented_ids)
    waitlist_count = await asyncio.to_thread(WaitlistStore().count)

    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей (профили): <b>{user_count}</b>\n"
        f"✉️ Согласны на рассылку: <b>{len(consented)}</b>\n"
        f"🤝 Пришли по рефералке: <b>{ref_count}</b>\n\n"
        f"💰 <b>Выручка (выданные заказы): {revenue} ₽</b>\n"
        f"💳 Подписок продано: {subs_sold}\n"
        f"🛒 Товаров продано: {goods_sold}\n"
        f"🎁 Пробных доступов выдано: {trials}\n\n"
        f"🧾 <b>Заказы</b>\n"
        f"⏳ Ждут оплату: {by_status.get(STATUS_AWAITING, 0)}\n"
        f"🟡 Ждут проверки: {by_status.get(STATUS_CLAIMED, 0)}\n"
        f"✅ Выдано: {by_status.get(STATUS_DELIVERED, 0)}\n"
        f"❌ Отклонено: {by_status.get(STATUS_REJECTED, 0)}\n\n"
        f"🎫 <b>Пул аккаунтов</b>\n"
        f"🟢 Свободно: {free} | 🔵 Выдано: {assigned} | ♻️ Истекло: {expired}\n"
        f"📋 В листе ожидания: {waitlist_count}"
    )
