"""Отдельный worker-процесс: фоновые задачи без Telegram-поллинга.

Запуск:  python -m app.worker_entry
В Docker: docker compose --profile worker up -d

Если бот запущен одним процессом (python -m app.main или start.bat) —
отдельный worker НЕ нужен: все фоновые задачи уже выполняются внутри
основного процесса (настройка RUN_BACKGROUND_TASKS=true в .env).

Отдельный worker имеет смысл на VPS при большой нагрузке. В этом случае
в основном процессе поставьте RUN_BACKGROUND_TASKS=false, чтобы задачи
не выполнялись дважды (двойные напоминания, двойные бэкапы).

Что делает worker:
1. Scheduler — мониторинг изменений ПЗЗ + истечение подписок.
2. reminder_loop — напоминания об окончании подписки, пробные доступы.
3. backup_loop — автобэкап данных раз в сутки.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Собрать сервисы и запустить фоновые задачи."""
    from app.bot.setup import create_bot
    from app.db.session import async_session_factory
    from app.integrations import NextGISClient, TelegramClient
    from app.repositories import (
        BatchItemRepo, BatchJobRepo, ChangeEventRepo, LayerSyncRepo,
        NotificationRepo, SubscriptionRepo, TrackedObjectRepo, UserRepo,
    )
    from app.services import (
        BatchService, MonitorService, NotificationService, SubscriptionService,
    )
    from app.services.backup_service import backup_loop
    from app.services.reminder_service import reminder_loop
    from app.workers import Scheduler

    bot = create_bot(settings.BOT_TOKEN)
    nextgis = NextGISClient()
    telegram = TelegramClient(bot)

    session = async_session_factory()
    sub_service = SubscriptionService(SubscriptionRepo(session), UserRepo(session))
    monitor_service = MonitorService(
        nextgis, TrackedObjectRepo(session), ChangeEventRepo(session),
        NotificationRepo(session), LayerSyncRepo(session),
    )
    batch_service = BatchService(nextgis, BatchJobRepo(session), BatchItemRepo(session))
    notif_service = NotificationService(NotificationRepo(session), telegram)

    services = {
        "subscription": sub_service,
        "monitor": monitor_service,
        "batch": batch_service,
        "notification": notif_service,
        "nextgis": nextgis,
        "telegram": telegram,
    }

    scheduler = Scheduler(services)
    await scheduler.start()
    logger.info("Worker запущен: планировщик + напоминания + автобэкап")

    try:
        await asyncio.gather(
            reminder_loop(bot, services),
            backup_loop(bot),
        )
    finally:
        await scheduler.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
