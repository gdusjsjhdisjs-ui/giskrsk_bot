"""Setup bot: Bot, Dispatcher, middleware, handlers, error handler."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from app.bot.handlers import (
    start_router, parcel_router, tariffs_router,
    subscription_router, tracking_router, batch_router,
    profile_router, help_router, admin_router, ai_router,
    account_router, convert_router, shop_router,
    registration_router, webapp_router, stats_router,
    torgi_router, clip_router, myorders_router,
)
from app.bot.middlewares import (
    ServiceInjectorMiddleware, DailyLimitMiddleware, LoggingMiddleware,
)

logger = logging.getLogger(__name__)


_ALERT_COOLDOWN = 600  # не чаще раза в 10 минут на тип ошибки
_last_alerts: dict[str, float] = {}


async def global_error_handler(event: ErrorEvent, bot: Bot) -> None:
    """Catch all unhandled bot errors, log them and alert admins."""
    logger.error("Bot error: %s", event.exception, exc_info=event.exception)

    # 🚨 Алерт админам в Telegram (с защитой от спама)
    import html
    import time

    from app.core.config import settings

    exc = event.exception
    key = type(exc).__name__
    now = time.monotonic()
    if now - _last_alerts.get(key, -_ALERT_COOLDOWN) < _ALERT_COOLDOWN:
        return
    _last_alerts[key] = now
    text = (
        f"🚨 <b>Ошибка в боте</b>\n"
        f"<code>{key}: {html.escape(str(exc))[:300]}</code>"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            pass


def create_dispatcher(
    services: dict | None = None,
    repos: dict | None = None,
    session_factory=None,
    repo_factories: dict | None = None,
) -> Dispatcher:
    """Create and configure aiogram Dispatcher."""
    dp = Dispatcher()

    # Global error handler
    dp.errors.register(global_error_handler)

    # Routers
    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(parcel_router)
    dp.include_router(tariffs_router)
    dp.include_router(subscription_router)
    dp.include_router(tracking_router)
    dp.include_router(batch_router)
    dp.include_router(profile_router)
    dp.include_router(help_router)
    dp.include_router(admin_router)
    dp.include_router(ai_router)
    dp.include_router(account_router)
    dp.include_router(convert_router)
    dp.include_router(shop_router)
    dp.include_router(webapp_router)
    dp.include_router(stats_router)
    dp.include_router(torgi_router)
    dp.include_router(clip_router)
    dp.include_router(myorders_router)

    # Middleware (order matters!)
    if services or repos or session_factory:
        dp.update.middleware(ServiceInjectorMiddleware(
            services=services or {},
            repos=repos or {},
            session_factory=session_factory,
            repo_factories=repo_factories or {},
        ))
    dp.update.middleware(DailyLimitMiddleware())
    dp.update.middleware(LoggingMiddleware())

    return dp


def create_bot(token: str) -> Bot:
    """Create aiogram Bot with system proxy support."""
    from aiogram.client.session.aiohttp import AiohttpSession

    proxy_url = None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            if winreg.QueryValueEx(key, "ProxyEnable")[0]:
                server = winreg.QueryValueEx(key, "ProxyServer")[0]
                if server:
                    proxy_url = "http://" + server.lstrip("http://")
                    logger.info("Using proxy: %s", proxy_url)
    except Exception:
        pass

    session = None
    if proxy_url:
        try:
            import aiohttp_socks  # noqa: F401

            session = AiohttpSession(proxy=proxy_url)
        except ImportError:
            logger.warning(
                "Найден системный прокси %s, но пакет aiohttp-socks не установлен — "
                "подключаемся к Telegram без прокси",
                proxy_url,
            )
    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
