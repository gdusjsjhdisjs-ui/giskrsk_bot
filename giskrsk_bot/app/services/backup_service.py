"""Автобэкап данных бота (раз в сутки).

Складывает JSON-хранилища и SQLite-базу в zip в папке backups/,
внутрь кладёт MANIFEST.txt с описанием содержимого и инструкцией
восстановления. Секреты (.env) в бэкап НЕ включаются.
Хранит последние 14 копий и отправляет свежий архив первому админу
в Telegram — резервная копия есть даже при поломке диска.
"""

from __future__ import annotations

import asyncio
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[2]
_BACKUP_DIR = _BASE_DIR / "backups"
_KEEP_LAST = 14
_DATA_FILES = (
    "webgis_dev.db",
    "account_pool.json",
    "user_profiles.json",
    "shop_orders.json",
    "shop_photos.json",
    "referrals.json",
    "reminders_state.json",
    "waitlist.json",
)


_FILE_DESCRIPTIONS = {
    "webgis_dev.db": "база SQLite (пользователи, подписки, платежи; режим USE_SQLITE)",
    "account_pool.json": "пул аккаунтов NextGIS и кому они выданы",
    "user_profiles.json": "профили пользователей бота",
    "shop_orders.json": "заказы магазина и подписок",
    "shop_photos.json": "скриншоты оплат",
    "referrals.json": "реферальные связи и бонусы",
    "reminders_state.json": "какие напоминания уже отправлены",
    "waitlist.json": "лист ожидания аккаунтов",
}


def _manifest_text(stamp: str) -> str:
    """Текст MANIFEST.txt — что лежит в бэкапе и как восстановиться."""
    lines = [
        "Автобэкап данных бота «ГИС Красноярье» (v13)",
        f"Создан (UTC): {stamp}",
        "",
        "Восстановление: положите файлы из архива в корень папки бота",
        "(рядом со start.bat) и перезапустите бота.",
        "",
        "Содержимое:",
    ]
    for name, descr in _FILE_DESCRIPTIONS.items():
        lines.append(f"  {name} — {descr}")
    lines += ["", "Секреты (.env) в бэкап не включаются."]
    return "\n".join(lines)


def make_backup() -> Path | None:
    """Создать zip-архив с данными. None — если бэкапить нечего."""
    _BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    target = _BACKUP_DIR / f"backup_{stamp}.zip"
    added = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _DATA_FILES:
            path = _BASE_DIR / name
            if path.exists():
                zf.write(path, arcname=name)
                added += 1
        if added:
            zf.writestr("MANIFEST.txt", _manifest_text(stamp))
    if not added:
        target.unlink(missing_ok=True)
        return None
    # Чистим старые копии
    backups = sorted(_BACKUP_DIR.glob("backup_*.zip"))
    for old in backups[:-_KEEP_LAST]:
        old.unlink(missing_ok=True)
    return target


async def backup_tick(bot: Bot) -> None:
    """Один бэкап + отправка админу."""
    target = await asyncio.to_thread(make_backup)
    if target is None:
        return
    logger.info("Бэкап создан: %s", target)
    admin_ids = list(settings.ADMIN_IDS)
    if not admin_ids:
        return
    try:
        await bot.send_document(
            admin_ids[0],
            FSInputFile(target),
            caption=f"💾 Автобэкап данных бота ({target.name})",
            disable_notification=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось отправить бэкап админу: %s", exc)


async def backup_loop(bot: Bot, interval_seconds: int = 24 * 3600) -> None:
    """Бесконечный цикл бэкапов (запускается из main.py)."""
    await asyncio.sleep(60)  # даём боту стартовать
    while True:
        try:
            await backup_tick(bot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка автобэкапа: %s", exc)
        await asyncio.sleep(interval_seconds)
