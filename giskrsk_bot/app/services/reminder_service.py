"""Фоновые напоминания и автоосвобождение аккаунтов.

Раз в час бот:
1. Напоминает клиентам за 3 дня и за 1 день до окончания подписки.
2. Помечает истёкшие подписки, сообщает клиенту и автоматически
   освобождает аккаунт из пула (статус «истёк» — админу приходит
   инструкция сменить пароль и вернуть аккаунт в пул).
3. Закрывает истёкшие пробные доступы (24 часа).

Состояние отправленных напоминаний: reminders_state.json.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards_data import SubPayAction
from app.core.config import settings
from app.services.account_pool import AccountPool
from app.services.profile_store import ProfileStore

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[2]
_STATE_FILE = _BASE_DIR / "reminders_state.json"

_PLAN_NAMES = {
    "basic_30d": "Basic — 30 дней",
    "pro_30d": "Pro — 30 дней",
    "pro_90d": "Pro — 90 дней",
    "year": "Pro — 12 месяцев",
}

_REMIND_STAGES = (3, 1)  # за сколько дней напоминать

_pool: AccountPool | None = None


def _get_pool() -> AccountPool:
    """Один экземпляр пула на процесс — не перечитываем файл каждый тик."""
    global _pool
    if _pool is None:
        _pool = AccountPool()
    return _pool


def _renew_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Продлить» прямо в напоминании — меньше шагов до оплаты."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🔄 Продлить подписку",
                callback_data=SubPayAction(action="list").pack(),
            )
        ]]
    )


def _load_state() -> dict[str, Any]:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    _STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _aware(dt: datetime) -> datetime:
    """SQLite может отдавать наивные даты — приводим к UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _notify_admins(bot: Bot, text: str) -> None:
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, exc)


async def reminder_tick(bot: Bot, services: dict) -> None:
    """Один проход всех фоновых проверок."""
    now = datetime.now(timezone.utc)
    state = _load_state()
    pool = _get_pool()
    sub_service = services.get("subscription")

    if sub_service:
        # 1. Напоминания об окончании подписки
        try:
            active_subs = await sub_service.sub_repo.get_all_active()
        except Exception as exc:  # noqa: BLE001
            logger.error("Не удалось получить активные подписки: %s", exc)
            active_subs = []
        reminded: dict[str, list[int]] = state.setdefault("reminded", {})
        for sub in active_subs:
            expires = _aware(sub.expires_at)
            days_left = (expires - now).days
            sent = reminded.setdefault(str(sub.id), [])
            for stage in _REMIND_STAGES:
                if 0 <= days_left <= stage and stage not in sent:
                    plan = _PLAN_NAMES.get(sub.plan_code, sub.plan_code)
                    try:
                        await bot.send_message(
                            sub.telegram_id,
                            f"⏳ Подписка «{plan}» заканчивается "
                            f"<b>{expires.strftime('%d.%m.%Y')}</b>.\n"
                            f"Продлите заранее, чтобы не потерять доступ "
                            f"к карте: /tariffs",
                            reply_markup=_renew_keyboard(),
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Напоминание не доставлено %s: %s",
                            sub.telegram_id, exc,
                        )
                    sent.append(stage)
                    # Сохраняем сразу — при рестарте бота напоминание
                    # не отправится повторно
                    _save_state(state)
                    break

        # 2. Истёкшие подписки + автоосвобождение аккаунтов из пула
        try:
            expired = await sub_service.expire_overdue()
        except Exception as exc:  # noqa: BLE001
            logger.error("Не удалось обработать истёкшие подписки: %s", exc)
            expired = []
        for item in expired:
            tid = item["telegram_id"]
            try:
                await bot.send_message(
                    tid,
                    "😔 Ваша подписка закончилась — доступ к карте "
                    "приостановлен.\nПродлить: /tariffs",
                    reply_markup=_renew_keyboard(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Не удалось написать клиенту %s: %s", tid, exc)
            account = pool.find_by_user(tid)
            if account:
                pool.mark_expired(account["login"])
                await _notify_admins(
                    bot,
                    f"♻️ Подписка клиента <code>{tid}</code> истекла.\n"
                    f"Аккаунт <code>{account['login']}</code> помечен «истёк».\n\n"
                    f"1) Смените пароль этого аккаунта в NextGIS Web;\n"
                    f"2) Верните его в пул: "
                    f"<code>/add_account {account['login']} новый_пароль</code>",
                )

    # 3. Пробные доступы (24 часа)
    profiles = ProfileStore()
    for profile in profiles.all_profiles():
        trial_until = profile.get("trial_until")
        if not trial_until or profile.get("trial_closed"):
            continue
        try:
            until = _aware(datetime.fromisoformat(trial_until))
        except ValueError:
            continue
        if now < until:
            continue
        uid = profile["user_id"]
        try:
            await bot.send_message(
                uid,
                "⏰ Пробный день закончился. Понравилось?\n"
                "Полный доступ к карте и боту — /tariffs 😉",
                reply_markup=_renew_keyboard(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось написать клиенту %s: %s", uid, exc)
        login = profile.get("trial_login")
        if login:
            pool.mark_expired(login)
            await _notify_admins(
                bot,
                f"⏰ Пробный доступ клиента <code>{uid}</code> истёк.\n"
                f"Аккаунт <code>{login}</code> помечен «истёк».\n\n"
                f"1) Смените пароль в NextGIS Web;\n"
                f"2) Верните в пул: "
                f"<code>/add_account {login} новый_пароль</code>",
            )
        profiles.upsert(uid, trial_closed=True)

    _save_state(state)


async def reminder_loop(
    bot: Bot, services: dict, interval_seconds: int = 3600
) -> None:
    """Бесконечный цикл фоновых проверок (запускается из main.py)."""
    await asyncio.sleep(20)  # даём боту стартовать
    while True:
        try:
            await reminder_tick(bot, services)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка фоновой проверки напоминаний: %s", exc)
        await asyncio.sleep(interval_seconds)
