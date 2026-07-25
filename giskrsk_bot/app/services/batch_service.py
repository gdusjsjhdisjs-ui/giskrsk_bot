"""Сервис пакетной проверки участков (CSV → результат)."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from uuid import UUID

from app.core.exceptions import InvalidCadastralNumberError
from app.integrations.nextgis import NextGISClient
from app.repositories.batch_job_repo import BatchJobRepo
from app.repositories.batch_item_repo import BatchItemRepo
from app.services.parcel_service import normalize_cadnum

logger = logging.getLogger(__name__)


class BatchService:
    """Пакетная проверка списка кадастровых номеров."""

    def __init__(
        self,
        nextgis: NextGISClient,
        batch_job_repo: BatchJobRepo,
        batch_item_repo: BatchItemRepo,
    ) -> None:
        self.nextgis = nextgis
        self.batch_job_repo = batch_job_repo
        self.batch_item_repo = batch_item_repo

    async def parse_csv(self, content: bytes) -> list[str]:
        """Разобрать CSV и извлечь кадастровые номера."""
        text = content.decode("utf-8-sig")  # BOM-safe
        reader = csv.reader(io.StringIO(text))
        cadnums = []
        for row in reader:
            if not row:
                continue
            # Берём первую непустую колонку
            for cell in row:
                cell = cell.strip()
                if cell and re.search(r"\d{2}:\d{2}", cell):
                    cadnums.append(cell)
                    break
        return cadnums

    async def create_job(self, telegram_id: int, raw_cadnums: list[str]) -> UUID:
        """Создать задачу и элементы."""
        # Создаём задачу
        job = await self.batch_job_repo.create(telegram_id)

        # Подготавливаем элементы
        items = []
        for i, raw in enumerate(raw_cadnums):
            items.append({
                "batch_job_id": job.id,
                "row_number": i + 1,
                "input_value": raw,
            })

        # Сохраняем элементы
        await self.batch_item_repo.create_bulk(items)
        await self.batch_job_repo.update_counts(job.id, total=len(items))

        return job.id

    async def process_job(self, job_id: UUID) -> dict:
        """Обработать задачу: проверить каждый КН через NextGIS."""
        job = await self.batch_job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        await self.batch_job_repo.update_status(job_id, "processing")
        items = await self.batch_item_repo.get_by_job_id(job_id)

        success = 0
        errors = 0

        for item in items:
            try:
                cadnum = normalize_cadnum(item.input_value)
                if not cadnum:
                    await self.batch_item_repo.update_result(
                        item.id, "invalid_format",
                        error_message="Неверный формат кадастрового номера",
                    )
                    errors += 1
                    await self.batch_job_repo.update_counts(job_id, processed=success + errors)
                    continue

                # Поиск в NextGIS
                data = await self.nextgis.search_by_cadnum(cadnum)
                if data:
                    await self.batch_item_repo.update_result(
                        item.id, "ok",
                        normalized_cadnum=cadnum,
                        result_json=data,
                    )
                    success += 1
                else:
                    await self.batch_item_repo.update_result(
                        item.id, "not_found",
                        normalized_cadnum=cadnum,
                        error_message="Участок не найден",
                    )
                    errors += 1

            except Exception as e:
                logger.error("Batch item error: %s", e)
                await self.batch_item_repo.update_result(
                    item.id, "api_error",
                    error_message=str(e),
                )
                errors += 1

            await self.batch_job_repo.update_counts(
                job_id, processed=success + errors, success=success, errors=errors,
            )

        # Завершаем
        status = "completed" if errors == 0 else "completed_with_errors"
        await self.batch_job_repo.update_status(job_id, status)

        return {
            "job_id": str(job_id),
            "total": job.total_rows,
            "success": success,
            "errors": errors,
            "status": status,
        }

    async def get_results_csv(self, job_id: UUID) -> bytes:
        """Сформировать CSV с результатами."""
        items = await self.batch_item_repo.get_by_job_id(job_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["№", "Введено", "Нормализованный КН", "Статус", "Ошибка"])

        for item in items:
            writer.writerow([
                item.row_number,
                item.input_value,
                item.normalized_cadnum or "",
                item.status,
                item.error_message or "",
            ])

        return output.getvalue().encode("utf-8-sig")

    async def get_results_json(self, job_id: UUID) -> dict:
        """Получить результаты задачи."""
        items = await self.batch_item_repo.get_by_job_id(job_id)
        stats = await self.batch_item_repo.get_stats(job_id)
        return {
            "job_id": str(job_id),
            "stats": stats,
            "items": [
                {
                    "row_number": item.row_number,
                    "input_value": item.input_value,
                    "normalized_cadnum": item.normalized_cadnum,
                    "status": item.status,
                    "error_message": item.error_message,
                }
                for item in items
            ],
        }

    async def get_user_jobs(self, telegram_id: int, limit: int = 10) -> list[dict]:
        """Получить задачи пользователя."""
        jobs = await self.batch_job_repo.get_user_jobs(telegram_id, limit)
        return [
            {
                "id": str(j.id),
                "status": j.status,
                "total": j.total_rows,
                "success": j.success_rows,
                "errors": j.error_rows,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
