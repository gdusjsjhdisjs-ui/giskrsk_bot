"""Планировщик cron-задач."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class Scheduler:
    """Фоновый планировщик для периодических задач."""

    def __init__(self, services: dict) -> None:
        self.services = services
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Запустить все фоновые задачи."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_monitor()),
            asyncio.create_task(self._run_expiry_check()),
        ]
        logger.info("Scheduler started with %d tasks", len(self._tasks))

    async def stop(self) -> None:
        """Остановить все фоновые задачи."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Scheduler stopped")

    async def _run_monitor(self) -> None:
        """Периодическая проверка изменений ПЗЗ."""
        interval = settings.MONITOR_CHECK_INTERVAL_MINUTES * 60
        monitor = self.services.get("monitor")
        if not monitor:
            logger.warning("Monitor service not available, scheduler skipping")
            return

        while self._running:
            try:
                await asyncio.sleep(interval)
                result = await monitor.check_layer_updates()
                if result.get("updated"):
                    logger.info("Layer update detected: %s", result)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Monitor check error: %s", e)

    async def _run_expiry_check(self) -> None:
        """Периодическая проверка истекших подписок (раз в час)."""
        sub_service = self.services.get("subscription")
        if not sub_service:
            logger.warning("Subscription service not available, expiry check skipping")
            return

        while self._running:
            try:
                await asyncio.sleep(3600)  # каждый час
                expired = await sub_service.expire_overdue()
                if expired:
                    logger.info("Expired %d subscriptions", len(expired))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Expiry check error: %s", e)
