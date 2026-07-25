"""Фоновые задачи (ARQ)."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_batch_job(ctx, job_id: str) -> dict:
    """Обработать batch-задачу (вызывается из ARQ)."""
    # Получаем сервисы из контекста
    services = ctx.get("services", {})
    batch_service = services.get("batch")
    if not batch_service:
        return {"status": "error", "message": "Batch service not available"}

    try:
        result = await batch_service.process_job(UUID(job_id))
        return result
    except Exception as e:
        logger.error("Batch job %s failed: %s", job_id, e)
        return {"status": "failed", "error": str(e)}


async def check_monitor(ctx) -> dict:
    """Проверить изменения ПЗЗ для всех отслеживаемых участков."""
    services = ctx.get("services", {})
    monitor_service = services.get("monitor")
    if not monitor_service:
        return {"status": "error", "message": "Monitor service not available"}

    try:
        result = await monitor_service.check_layer_updates()
        return result
    except Exception as e:
        logger.error("Monitor check failed: %s", e)
        return {"status": "failed", "error": str(e)}


async def send_pending_notifications(ctx) -> dict:
    """Отправить ожидающие уведомления."""
    services = ctx.get("services", {})
    notification_service = services.get("notification")
    if not notification_service:
        return {"status": "error", "message": "Notification service not available"}

    try:
        sent = await notification_service.process_pending()
        return {"status": "ok", "sent": sent}
    except Exception as e:
        logger.error("Notification send failed: %s", e)
        return {"status": "failed", "error": str(e)}


async def expire_subscriptions(ctx) -> dict:
    """Истечение просроченных подписок."""
    services = ctx.get("services", {})
    sub_service = services.get("subscription")
    if not sub_service:
        return {"status": "error", "message": "Subscription service not available"}

    try:
        expired = await sub_service.expire_overdue()
        return {"status": "ok", "expired_count": len(expired)}
    except Exception as e:
        logger.error("Expire subscriptions failed: %s", e)
        return {"status": "failed", "error": str(e)}
