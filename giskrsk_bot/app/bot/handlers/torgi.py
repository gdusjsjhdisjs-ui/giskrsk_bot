"""Аукционы torgi.gov.ru: поиск извещений по населённому пункту.

Использует публичный API портала (ключи не нужны). Если портал меняет
формат ответа или недоступен — бот честно сообщает об этом клиенту.
"""

from __future__ import annotations

import html
import logging

import httpx
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router(name="torgi")

_API_URL = "https://torgi.gov.ru/new/api/public/lotcards/search"
_LOT_URL = "https://torgi.gov.ru/new/public/lots/lot"

_USAGE = (
    "🏛 <b>Поиск торгов на torgi.gov.ru</b>\n\n"
    "Напишите команду и населённый пункт (или любой запрос):\n"
    "<code>/torgi Емельяново</code>\n"
    "<code>/torgi Дивногорск земельный участок</code>\n\n"
    "Бот покажет 5 свежих извещений со ссылками."
)


def _fmt_price(value) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "не указана"
    return f"{amount:,.0f} ₽".replace(",", " ")


@router.message(Command("torgi"))
async def cmd_torgi(message: Message, command: CommandObject) -> None:
    """Поиск активных извещений по текстовому запросу."""
    query = (command.args or "").strip()
    if not query:
        await message.answer(_USAGE)
        return

    params = {
        "lotStatus": "PUBLISHED",
        "text": query,
        "size": 5,
        "page": 0,
        "sort": "firstVersionPublicationDate,desc",
        "byFirstVersion": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                _API_URL,
                params=params,
                headers={"User-Agent": "Mozilla/5.0 (compatible; GisKrskBot/1.0)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("torgi.gov.ru недоступен: %s", exc)
        await message.answer(
            "😔 Сервис torgi.gov.ru сейчас не отвечает. Попробуйте позже."
        )
        return

    lots = data.get("content") or []
    if not lots:
        await message.answer(
            f"🔍 По запросу «{html.escape(query)}» активных извещений не найдено.\n"
            f"Попробуйте другое написание или более короткий запрос."
        )
        return

    total = data.get("totalElements") or len(lots)
    lines = [
        f"🏛 <b>Торги по запросу «{html.escape(query)}»</b> (найдено: {total})"
    ]
    for lot in lots:
        name = html.escape(str(lot.get("lotName") or "Без названия"))[:150]
        price = _fmt_price(lot.get("priceMin") or lot.get("startPrice"))
        end = str(lot.get("biddEndTime") or "")[:10]
        lot_id = lot.get("id")
        line = f"▪️ {name}\n💰 Начальная цена: {price}"
        if end:
            line += f" | 📅 Заявки до {end}"
        if lot_id:
            line += f'\n🔗 <a href="{_LOT_URL}/{lot_id}">Открыть извещение</a>'
        lines.append(line)
    lines.append("Ещё больше — на https://torgi.gov.ru")
    await message.answer("\n\n".join(lines), disable_web_page_preview=True)
