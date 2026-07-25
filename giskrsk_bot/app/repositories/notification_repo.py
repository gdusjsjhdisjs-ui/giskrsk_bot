"""Репозиторий уведомлений."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification


class NotificationRepo:
    """CRUD для таблицы notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        telegram_id: int,
        change_event_id: UUID,
        message_text: str | None = None,
    ) -> Notification:
        """Создать уведомление."""
        notif = Notification(
            telegram_id=telegram_id,
            change_event_id=change_event_id,
            message_text=message_text,
            status="pending",
        )
        self.session.add(notif)
        await self.session.commit()
        await self.session.refresh(notif)
        return notif

    async def get_pending(self) -> list[Notification]:
        """Получить неотправленные уведомления."""
        stmt = (
            select(Notification)
            .where(Notification.status == "pending")
            .order_by(Notification.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, notif_id: UUID) -> None:
        """Отметить уведомление как отправленное."""
        stmt = select(Notification).where(Notification.id == notif_id)
        result = await self.session.execute(stmt)
        notif = result.scalar_one_or_none()
        if notif:
            notif.status = "sent"
            notif.sent_at = func.now()
            await self.session.commit()

    async def mark_failed(self, notif_id: UUID) -> None:
        """Отметить уведомление как неудачное."""
        stmt = select(Notification).where(Notification.id == notif_id)
        result = await self.session.execute(stmt)
        notif = result.scalar_one_or_none()
        if notif:
            notif.status = "failed"
            await self.session.commit()

    async def get_user_notifications(self, telegram_id: int, limit: int = 20) -> list[Notification]:
        """Получить уведомления пользователя."""
        stmt = (
            select(Notification)
            .where(Notification.telegram_id == telegram_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_count(self) -> int:
        """Количество неотправленных уведомлений."""
        stmt = select(func.count()).select_from(Notification).where(Notification.status == "pending")
        result = await self.session.execute(stmt)
        return result.scalar() or 0
