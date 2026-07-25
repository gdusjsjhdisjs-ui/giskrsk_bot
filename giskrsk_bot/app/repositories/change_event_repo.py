"""Репозиторий событий изменений."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChangeEvent


class ChangeEventRepo:
    """CRUD для таблицы change_events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        tracked_object_id: UUID,
        event_type: str,
        old_values: dict | None = None,
        new_values: dict | None = None,
    ) -> ChangeEvent:
        """Записать событие изменения."""
        event = ChangeEvent(
            tracked_object_id=tracked_object_id,
            event_type=event_type,
            old_values=old_values,
            new_values=new_values,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def get_by_tracked_object(self, tracked_object_id: UUID, limit: int = 20) -> list[ChangeEvent]:
        """Получить историю изменений объекта."""
        stmt = (
            select(ChangeEvent)
            .where(ChangeEvent.tracked_object_id == tracked_object_id)
            .order_by(ChangeEvent.detected_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 50) -> list[ChangeEvent]:
        """Последние изменения (для ленты)."""
        stmt = select(ChangeEvent).order_by(ChangeEvent.detected_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
