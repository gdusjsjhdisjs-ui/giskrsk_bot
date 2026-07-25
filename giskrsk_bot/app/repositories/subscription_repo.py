"""Репозиторий подписок."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscription


class SubscriptionRepo:
    """CRUD для таблицы subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        telegram_id: int,
        plan_code: str,
        expires_at: datetime,
        payment_id: UUID | None = None,
    ) -> Subscription:
        """Создать подписку."""
        sub = Subscription(
            telegram_id=telegram_id,
            plan_code=plan_code,
            status="active",
            payment_id=payment_id,
            expires_at=expires_at,
        )
        self.session.add(sub)
        await self.session.commit()
        await self.session.refresh(sub)
        return sub

    async def get_by_id(self, sub_id: UUID) -> Subscription | None:
        """Получить подписку по ID."""
        stmt = select(Subscription).where(Subscription.id == sub_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self, telegram_id: int) -> Subscription | None:
        """Получить активную подписку пользователя."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Subscription)
            .where(
                Subscription.telegram_id == telegram_id,
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[Subscription]:
        """Получить все активные подписки."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Subscription)
            .where(Subscription.status == "active", Subscription.expires_at > now)
            .order_by(Subscription.expires_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def expire_overdue(self) -> list[Subscription]:
        """Истекшие подписки → статус expired. Возвращает список."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Subscription)
            .where(Subscription.status == "active", Subscription.expires_at <= now)
        )
        result = await self.session.execute(stmt)
        expired = list(result.scalars().all())
        for sub in expired:
            sub.status = "expired"
        if expired:
            await self.session.commit()
        return expired

    async def extend(self, sub_id: UUID, new_expires_at: datetime) -> None:
        """Продлить подписку."""
        stmt = select(Subscription).where(Subscription.id == sub_id)
        result = await self.session.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub:
            sub.expires_at = new_expires_at
            sub.status = "active"
            await self.session.commit()

    async def cancel(self, sub_id: UUID) -> None:
        """Отменить подписку."""
        stmt = select(Subscription).where(Subscription.id == sub_id)
        result = await self.session.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = "canceled"
            await self.session.commit()

    async def get_user_subscriptions(self, telegram_id: int, limit: int = 10) -> list[Subscription]:
        """История подписок пользователя."""
        stmt = (
            select(Subscription)
            .where(Subscription.telegram_id == telegram_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_count(self) -> int:
        """Количество активных подписок."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status == "active", Subscription.expires_at > now)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
