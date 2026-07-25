"""Репозиторий состояния синхронизации слоёв."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LayerSyncState


class LayerSyncRepo:
    """CRUD для таблицы layer_sync_state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, layer_key: str) -> LayerSyncState | None:
        """Получить состояние слоя."""
        stmt = select(LayerSyncState).where(LayerSyncState.layer_key == layer_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        layer_key: str,
        ngw_resource_id: int,
        last_seen_version: int = 0,
    ) -> LayerSyncState:
        """Создать или обновить состояние слоя."""
        existing = await self.get(layer_key)
        if existing:
            existing.ngw_resource_id = ngw_resource_id
            existing.last_seen_version = last_seen_version
            existing.status = "active"
        else:
            existing = LayerSyncState(
                layer_key=layer_key,
                ngw_resource_id=ngw_resource_id,
                last_seen_version=last_seen_version,
                status="active",
            )
            self.session.add(existing)
        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def update_version(self, layer_key: str, version: int) -> None:
        """Обновить версию слоя."""
        state = await self.get(layer_key)
        if state:
            state.last_seen_version = version
            await self.session.commit()

    async def mark_error(self, layer_key: str) -> None:
        """Отметить ошибку синхронизации."""
        state = await self.get(layer_key)
        if state:
            state.status = "error"
            await self.session.commit()

    async def get_all_active(self) -> list[LayerSyncState]:
        """Получить все активные слои."""
        stmt = select(LayerSyncState).where(LayerSyncState.status == "active")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
