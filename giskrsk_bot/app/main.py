"""Основной модуль приложения: FastAPI + aiogram."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import health_router, webhooks_router, admin_router
from app.bot.setup import create_bot, create_dispatcher
from app.core.config import settings
from app.db.session import async_session_factory

# ── Логирование ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Инициализация сервисов и репозиториев ────────────────────────────────
def init_services_and_repos() -> tuple[dict, dict]:
    """Создать все сервисы и репозитории."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async def get_session() -> AsyncSession:
        async with async_session_factory() as session:
            return session

    # Репозитории
    from app.repositories import (
        UserRepo, PaymentRepo, WebhookEventRepo, SubscriptionRepo,
        TrackedObjectRepo, ChangeEventRepo, NotificationRepo,
        BatchJobRepo, BatchItemRepo, LayerSyncRepo,
    )

    # Интеграции
    from app.integrations import (
        GeoServiceClient, NextGISClient, RedisCache, TelegramClient, YooKassaClient,
    )

    # Сервисы
    from app.services import (
        ParcelService, PaymentService, WebhookProcessor,
        SubscriptionService, BatchService, NotificationService,
        MonitorService, PdfService,
    )

    # Создаём клиенты
    nextgis = NextGISClient()
    geoservice = GeoServiceClient()
    yookassa = YooKassaClient()
    redis = RedisCache()
    telegram_client = TelegramClient()

    # Репозитории (будет использоваться с session)
    # NOTE: репозитории создаются в каждом хендлере из data['repos']
    # Здесь мы создаём фабрику для инъекции
    repo_factories = {
        "user": lambda s: UserRepo(s),
        "payment": lambda s: PaymentRepo(s),
        "webhook_event": lambda s: WebhookEventRepo(s),
        "subscription": lambda s: SubscriptionRepo(s),
        "tracked_object": lambda s: TrackedObjectRepo(s),
        "change_event": lambda s: ChangeEventRepo(s),
        "notification": lambda s: NotificationRepo(s),
        "batch_job": lambda s: BatchJobRepo(s),
        "batch_item": lambda s: BatchItemRepo(s),
        "layer_sync": lambda s: LayerSyncRepo(s),
    }

    # Сервисы (верхний уровень — используют репозитории через сессию)
    # Создаём сессию для сервисов, которые работают по запросу
    async def repos() -> dict:
        session = await get_session()
        return {name: factory(session) for name, factory in repo_factories.items()}

    # Сервисы (разделяем экземпляры)
    # NOTE: в реальной работе сервисы получают репозитории при вызове
    # Здесь — упрощённая инициализация для FastAPI lifespan
    services_dict: dict = {}
    repos_dict: dict = {}

    # Сохраняем клиенты интеграций для сервисов
    services_dict["nextgis"] = nextgis
    services_dict["yookassa"] = yookassa
    services_dict["redis"] = redis

    return services_dict, repos_dict


# ── Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация и завершение работы приложения."""
    logger.info("Starting ГИС Красноярье Telegram Bot...")

    # Создаём бота
    bot = create_bot(settings.BOT_TOKEN)

    # Создаём клиенты интеграций
    from app.integrations import NextGISClient, YooKassaClient, RedisCache, TelegramClient, GeoServiceClient
    from app.repositories import (
        UserRepo, PaymentRepo, WebhookEventRepo, SubscriptionRepo,
        TrackedObjectRepo, ChangeEventRepo, NotificationRepo,
        BatchJobRepo, BatchItemRepo, LayerSyncRepo,
    )
    from app.services import (
        ParcelService, PaymentService, WebhookProcessor,
        SubscriptionService, BatchService, NotificationService,
        MonitorService, PdfService, AiService, AccountManager,
    )

    nextgis = NextGISClient()
    geoservice = GeoServiceClient()
    yookassa = YooKassaClient()
    redis_cache = RedisCache()
    telegram = TelegramClient(bot)

    # Фабрики репозиториев: сессия создаётся на каждый Telegram-апдейт
    from app.db.session import async_session_factory as _session_factory
    repo_factories = {
        "user": lambda s: UserRepo(s),
        "payment": lambda s: PaymentRepo(s),
        "webhook_event": lambda s: WebhookEventRepo(s),
        "subscription": lambda s: SubscriptionRepo(s),
        "tracked_object": lambda s: TrackedObjectRepo(s),
        "change_event": lambda s: ChangeEventRepo(s),
        "notification": lambda s: NotificationRepo(s),
        "batch_job": lambda s: BatchJobRepo(s),
        "batch_item": lambda s: BatchItemRepo(s),
        "layer_sync": lambda s: LayerSyncRepo(s),
    }
    # Временная сессия для сервисов, которые держат репо (sub_service и др.)
    _init_session = _session_factory()
    session_repos = {
        "user": UserRepo(_init_session),
        "payment": PaymentRepo(_init_session),
        "webhook_event": WebhookEventRepo(_init_session),
        "subscription": SubscriptionRepo(_init_session),
        "tracked_object": TrackedObjectRepo(_init_session),
        "change_event": ChangeEventRepo(_init_session),
        "notification": NotificationRepo(_init_session),
        "batch_job": BatchJobRepo(_init_session),
        "batch_item": BatchItemRepo(_init_session),
        "layer_sync": LayerSyncRepo(_init_session),
    }

    # Создаём таблицы если их нет (SQLite dev mode)
    try:
        from app.db.base import Base
        from app.db.session import engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning("Could not create tables: %s", e)

    # Сервисы
    parcel_service = ParcelService(geoservice, nextgis, redis_cache)
    sub_service = SubscriptionService(session_repos["subscription"], session_repos["user"])
    payment_service = PaymentService(yookassa, session_repos["payment"], sub_service)
    webhook_processor = WebhookProcessor(session_repos["webhook_event"], session_repos["payment"], sub_service)
    batch_service = BatchService(nextgis, session_repos["batch_job"], session_repos["batch_item"])
    notif_service = NotificationService(session_repos["notification"], telegram)
    monitor_service = MonitorService(
        nextgis, session_repos["tracked_object"],
        session_repos["change_event"], session_repos["notification"],
        session_repos["layer_sync"],
    )
    pdf_service = PdfService()
    account_manager = AccountManager(nextgis)

    # Собираем сервисы
    services = {
        "parcel": parcel_service,
        "payment": payment_service,
        "webhook_processor": webhook_processor,
        "subscription": sub_service,
        "batch": batch_service,
        "notification": notif_service,
        "monitor": monitor_service,
        "pdf": pdf_service,
        "nextgis": nextgis,
        "geoservice": geoservice,
        "yookassa": yookassa,
        "redis": redis_cache,
        "telegram": telegram,
        "account_manager": account_manager,
        "ai": AiService(),
    }

    # Репозитории
    repos_dict = session_repos

    # Диспетчер: middleware создаёт свежие репо на каждый апдейт
    dp = create_dispatcher(
        services=services,
        repos=repos_dict,
        session_factory=_session_factory,
        repo_factories=repo_factories,
    )

    # Webhook processor для FastAPI
    app.state.webhook_processor = webhook_processor
    app.state.bot = bot
    app.state.dp = dp
    app.state.services = services
    app.state.repos = repos_dict

    # Запуск планировщика (мониторинг ПЗЗ + автоистечение подписок).
    # Если запускаете отдельный worker (python -m app.worker_entry),
    # поставьте в .env RUN_BACKGROUND_TASKS=false — иначе задачи пойдут дважды.
    if settings.RUN_BACKGROUND_TASKS:
        from app.workers import Scheduler
        scheduler = Scheduler(services)
        app.state.scheduler = scheduler
        await scheduler.start()

    # Webhook (продакшн) или polling
    WEBHOOK_PATH = "/webhook"
    if settings.APP_BASE_URL and "localhost" not in settings.APP_BASE_URL:
        await bot.set_webhook(
            url=f"{settings.APP_BASE_URL}{WEBHOOK_PATH}",
            allowed_updates=dp.resolve_used_update_types(),
        )
        logger.info("Webhook set to %s%s", settings.APP_BASE_URL, WEBHOOK_PATH)
    else:
        logger.info("Starting in polling mode")
        polling_task = asyncio.create_task(
            dp.start_polling(bot, skip_updates=True)
        )
        app.state.polling_task = polling_task

    # Фоновые напоминания: окончание подписок, автоосвобождение аккаунтов,
    # пробные доступы (24 часа)
    if settings.RUN_BACKGROUND_TASKS:
        from app.services.reminder_service import reminder_loop
        app.state.reminder_task = asyncio.create_task(reminder_loop(bot, services))

        # Автобэкап данных (раз в сутки, архив уходит первому админу)
        from app.services.backup_service import backup_loop
        app.state.backup_task = asyncio.create_task(backup_loop(bot))

    # Меню команд в интерфейсе Telegram (кнопка «/» у поля ввода)
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
            BotCommand(command="help", description="Справка по боту"),
        ])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось установить меню команд: %s", exc)

    logger.info("Bot started!")
    yield

    # Shutdown
    if hasattr(app.state, 'reminder_task'):
        app.state.reminder_task.cancel()
        try:
            await app.state.reminder_task
        except asyncio.CancelledError:
            pass
    if hasattr(app.state, 'backup_task'):
        app.state.backup_task.cancel()
        try:
            await app.state.backup_task
        except asyncio.CancelledError:
            pass
    if hasattr(app.state, 'polling_task'):
        app.state.polling_task.cancel()
        try:
            await app.state.polling_task
        except asyncio.CancelledError:
            pass
    if settings.APP_BASE_URL and "localhost" not in settings.APP_BASE_URL:
        await bot.delete_webhook()
    await nextgis.close()
    await yookassa.close()
    await redis_cache.close()
    await _init_session.close()
    await bot.session.close()
    logger.info("ГИС Красноярье Telegram Bot stopped.")


# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="ГИС Красноярье — Telegram Bot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация API роутов
app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(admin_router)


# ── Webhook endpoint для Telegram ────────────────────────────────────────
@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict:
    """Принять обновление от Telegram."""
    bot = request.app.state.bot
    dp = request.app.state.dp
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"status": "ok"}


# ── Запуск ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
