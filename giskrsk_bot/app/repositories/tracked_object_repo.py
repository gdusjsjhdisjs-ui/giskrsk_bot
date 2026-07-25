"""Репозиторий отслеживаемых участков."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrackedObject


class TrackedObjectRepo:
    """CRUD для таблицы tracked_objects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, telegram_id: int, cadastral_number: str) -> TrackedObject:
        """Добавить участок в отслеживание."""
        obj = TrackedObject(
            telegram_id=telegram_id,
            cadastral_number=cadastral_number,
            active=True,
        )
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def remove(self, track_id: UUID) -> None:
        """Удалить отслеживание."""
        stmt = select(TrackedObject).where(TrackedObject.id == track_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            await self.session.delete(obj)
            await self.session.commit()

    async def remove_by_cadnum(self, telegram_id: int, cadastral_number: str) -> None:
        """Удалить отслеживание по кадастровому номеру."""
        stmt = select(TrackedObject).where(
            TrackedObject.telegram_id == telegram_id,
            TrackedObject.cadastral_number == cadastral_number,
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            await self.session.delete(obj)
            await self.session.commit()

    async def get_user_tracked(self, telegram_id: int) -> list[TrackedObject]:
        """Получить все отслеживаемые участки пользователя."""
        stmt = (
            select(TrackedObject)
            .where(TrackedObject.telegram_id == telegram_id)
            .order_by(TrackedObject.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_active_tracked(self, telegram_id: int) -> list[TrackedObject]:
        """Получить активные отслеживания пользователя."""
        stmt = (
            select(TrackedObject)
            .where(
                TrackedObject.telegram_id == telegram_id,
                TrackedObject.active == True,
            )
            .order_by(TrackedObject.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_active(self) -> list[TrackedObject]:
        """Получить все активные отслеживания (для мониторинга)."""
        stmt = select(TrackedObject).where(TrackedObject.active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, track_id: UUID) -> TrackedObject | None:
        """Получить отслеживание по ID."""
        stmt = select(TrackedObject).where(TrackedObject.id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def toggle(self, track_id: UUID) -> bool:
        """Включить/выключить отслеживание. Возвращает новое состояние."""
        stmt = select(TrackedObject).where(TrackedObject.id == track_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            obj.active = not obj.active
            await self.session.commit()
            return obj.active
        return False

    async def update_snapshot(
        self,
        track_id: UUID,
        snapshot_hash: str,
        snapshot_payload: dict,
    ) -> None:
        """Обновить слепок данных участка."""
        stmt = select(TrackedObject).where(TrackedObject.id == track_id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj:
            obj.last_snapshot_hash = snapshot_hash
            obj.last_snapshot_payload = snapshot_payload
            obj.last_checked_at = func.now()
            await self.session.commit()

    async def get_user_count(self, telegram_id: int) -> int:
        """Количество отслеживаемых участков у пользователя."""
        stmt = select(func.count()).select_from(TrackedObject).where(
            TrackedObject.telegram_id == telegram_id,
            TrackedObject.active == True,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def exists(self, telegram_id: int, cadastral_number: str) -> bool:
        """Проверить, отслеживается ли уже участок."""
        stmt = select(TrackedObject).where(
            TrackedObject.telegram_id == telegram_id,
            TrackedObject.cadastral_number == cadastral_number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
