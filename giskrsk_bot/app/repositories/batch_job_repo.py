"""Репозиторий batch-задач."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BatchJob


class BatchJobRepo:
    """CRUD для таблицы batch_jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, telegram_id: int) -> BatchJob:
        """Создать batch-задачу."""
        job = BatchJob(telegram_id=telegram_id, status="uploaded")
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> BatchJob | None:
        """Получить задачу по ID."""
        stmt = select(BatchJob).where(BatchJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_jobs(self, telegram_id: int, limit: int = 10) -> list[BatchJob]:
        """Получить задачи пользователя."""
        stmt = (
            select(BatchJob)
            .where(BatchJob.telegram_id == telegram_id)
            .order_by(BatchJob.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, job_id: UUID, status: str) -> None:
        """Обновить статус."""
        stmt = select(BatchJob).where(BatchJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            if status == "processing":
                job.started_at = func.now()
            elif status in ("completed", "failed"):
                job.completed_at = func.now()
            await self.session.commit()

    async def update_counts(
        self,
        job_id: UUID,
        total: int | None = None,
        processed: int | None = None,
        success: int | None = None,
        errors: int | None = None,
    ) -> None:
        """Обновить счётчики."""
        stmt = select(BatchJob).where(BatchJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job:
            if total is not None:
                job.total_rows = total
            if processed is not None:
                job.processed_rows = processed
            if success is not None:
                job.success_rows = success
            if errors is not None:
                job.error_rows = errors
            await self.session.commit()

    async def set_result_path(self, job_id: UUID, result_path: str) -> None:
        """Сохранить путь к файлу результата."""
        stmt = select(BatchJob).where(BatchJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job:
            job.result_file_path = result_path
            await self.session.commit()

    async def get_pending_jobs(self) -> list[BatchJob]:
        """Получить задачи ожидающие обработки."""
        stmt = (
            select(BatchJob)
            .where(BatchJob.status == "uploaded")
            .order_by(BatchJob.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
