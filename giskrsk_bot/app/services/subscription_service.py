"""Сервис управления подписками."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.repositories.subscription_repo import SubscriptionRepo
from app.repositories.user_repo import UserRepo
# PLAN_DURATIONS маппинг: план -> длительность в днях
PLAN_DURATIONS: dict[str, int] = {
    "basic_30d": 30,
    "pro_30d": 30,
    "pro_90d": 90,
    "year": 365,
}

logger = logging.getLogger(__name__)

# Маппинг: план → роль пользователя
PLAN_ROLES: dict[str, str] = {
    "basic_30d": "basic",
    "pro_30d": "pro",
    "pro_90d": "pro",
    "year": "pro",
}

# Маппинг: план → дневной лимит
PLAN_LIMITS: dict[str, int] = {
    "basic_30d": settings.DAILY_LIMIT_BASIC,
    "pro_30d": settings.DAILY_LIMIT_PRO,
    "pro_90d": settings.DAILY_LIMIT_PRO,
    "year": settings.DAILY_LIMIT_PRO,
}


class SubscriptionService:
    """Активация, продление, проверка и истечение подписок."""

    def __init__(self, sub_repo: SubscriptionRepo, user_repo: UserRepo) -> None:
        self.sub_repo = sub_repo
        self.user_repo = user_repo

    async def activate(self, telegram_id: int, plan_code: str, payment_id: UUID | None = None) -> dict:
        """Активировать или продлить подписку."""
        # Получаем активную подписку
        existing = await self.sub_repo.get_active(telegram_id)
        if existing:
            # Продлеваем: новая дата = конец старой + длительность
            duration_days = PLAN_DURATIONS.get(plan_code, 30)
            new_expires = existing.expires_at + timedelta(days=duration_days)
            await self.sub_repo.extend(existing.id, new_expires)
            # Обновляем роль
            new_role = PLAN_ROLES.get(plan_code, "user")
            await self.user_repo.update_role(telegram_id, new_role)
            return {"subscription_id": str(existing.id), "expires_at": new_expires.isoformat(), "extended": True}
        else:
            # Новая подписка
            duration_days = PLAN_DURATIONS.get(plan_code, 30)
            expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
            sub = await self.sub_repo.create(telegram_id, plan_code, expires_at, payment_id)
            new_role = PLAN_ROLES.get(plan_code, "user")
            await self.user_repo.update_role(telegram_id, new_role)
            return {"subscription_id": str(sub.id), "expires_at": expires_at.isoformat(), "extended": False}

    async def get_active(self, telegram_id: int) -> dict | None:
        """Проверить активную подписку."""
        sub = await self.sub_repo.get_active(telegram_id)
        if not sub:
            return None
        return {
            "id": str(sub.id),
            "plan_code": sub.plan_code,
            "status": sub.status,
            "started_at": sub.created_at.isoformat() if sub.created_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "days_left": (sub.expires_at - datetime.now(timezone.utc)).days if sub.expires_at else 0,
        }

    async def get_daily_limit(self, telegram_id: int) -> int:
        """Получить дневной лимит пользователя."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return settings.DAILY_LIMIT_FREE
        if user.role == "admin":
            return 999999
        if user.role == "pro":
            return settings.DAILY_LIMIT_PRO
        if user.role == "basic":
            return settings.DAILY_LIMIT_BASIC
        return settings.DAILY_LIMIT_FREE

    async def get_role(self, telegram_id: int) -> str:
        """Получить роль пользователя."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        return user.role if user else "free"

    async def expire_overdue(self) -> list[dict]:
        """Истекшие подписки → expired. Возвращает список."""
        expired = await self.sub_repo.expire_overdue()
        for sub in expired:
            # Понижаем роль до free
            await self.user_repo.update_role(sub.telegram_id, "free")
            logger.info("Subscription expired for user %s", sub.telegram_id)
        return [
            {
                "telegram_id": sub.telegram_id,
                "plan_code": sub.plan_code,
                "expired_at": sub.expires_at.isoformat() if sub.expires_at else None,
            }
            for sub in expired
        ]

    async def cancel(self, telegram_id: int) -> bool:
        """Отменить подписку (не продлевать)."""
        sub = await self.sub_repo.get_active(telegram_id)
        if sub:
            await self.sub_repo.cancel(sub.id)
            await self.user_repo.update_role(telegram_id, "free")
            return True
        return False

    async def get_user_subscriptions(self, telegram_id: int, limit: int = 10) -> list[dict]:
        """История подписок."""
        subs = await self.sub_repo.get_user_subscriptions(telegram_id, limit)
        return [
            {
                "id": str(s.id),
                "plan_code": s.plan_code,
                "status": s.status,
                "started_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s in subs
        ]

    async def get_stats(self) -> dict:
        """Статистика подписок."""
        active_count = await self.sub_repo.get_active_count()
        return {"active_count": active_count}
