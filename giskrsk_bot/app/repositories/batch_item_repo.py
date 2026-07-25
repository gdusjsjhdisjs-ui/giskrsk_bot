"""Репозиторий элементов batch-задач."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BatchItem


class BatchItemRepo:
    """CRUD для таблицы batch_items."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_bulk(self, items: list[dict]) -> list[BatchItem]:
        """Массовое создание элементов."""
        objects = [
            BatchItem(
                batch_job_id=item["batch_job_id"],
                row_number=item["row_number"],
                input_value=item["input_value"],
            )
            for item in items
        ]
        self.session.add_all(objects)
        await self.session.commit()
        for obj in objects:
            await self.session.refresh(obj)
        return objects

    async def get_by_job_id(self, job_id: UUID) -> list[BatchItem]:
        """Получить все элементы задачи."""
        stmt = (
            select(BatchItem)
            .where(BatchItem.batch_job_id == job_id)
            .order_by(BatchItem.row_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_result(
        self,
        item_id: UUID,
        status: str,
        normalized_cadnum: str | None = None,
        error_message: str | None = None,
        result_json: dict | None = None,
    ) -> None:
        """Обновить результат обработки элемента."""
        stmt = select(BatchItem).where(BatchItem.id == item_id)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item:
            item.status = status
            if normalized_cadnum:
                item.normalized_cadnum = normalized_cadnum
            if error_message:
                item.error_message = error_message
            if result_json:
                item.result_json = result_json
            await self.session.commit()

    async def get_stats(self, job_id: UUID) -> dict:
        """Статистика по задаче."""
        total = await self._count(job_id)
        ok_count = await self._count_by_status(job_id, "ok")
        invalid = await self._count_by_status(job_id, "invalid_format")
        not_found = await self._count_by_status(job_id, "not_found")
        api_err = await self._count_by_status(job_id, "api_error")
        return {
            "total": total,
            "ok": ok_count,
            "invalid_format": invalid,
            "not_found": not_found,
            "api_error": api_err,
        }

    async def _count(self, job_id: UUID) -> int:
        stmt = select(func.count()).select_from(BatchItem).where(BatchItem.batch_job_id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _count_by_status(self, job_id: UUID, status: str) -> int:
        stmt = (
            select(func.count())
            .select_from(BatchItem)
            .where(BatchItem.batch_job_id == job_id, BatchItem.status == status)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
