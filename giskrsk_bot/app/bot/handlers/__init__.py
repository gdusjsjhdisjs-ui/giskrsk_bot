"""Импорт всех хендлеров."""

from app.bot.handlers.start import router as start_router
from app.bot.handlers.parcel import router as parcel_router
from app.bot.handlers.tariffs import router as tariffs_router
from app.bot.handlers.subscription import router as subscription_router
from app.bot.handlers.tracking import router as tracking_router
from app.bot.handlers.batch import router as batch_router
from app.bot.handlers.profile import router as profile_router
from app.bot.handlers.help import router as help_router
from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.ai_consultant import router as ai_router
from app.bot.handlers.account import router as account_router
from app.bot.handlers.convert import router as convert_router
from app.bot.handlers.shop import router as shop_router
from app.bot.handlers.registration import router as registration_router
from app.bot.handlers.webapp import router as webapp_router
from app.bot.handlers.stats import router as stats_router
from app.bot.handlers.torgi import router as torgi_router
from app.bot.handlers.clip_order import router as clip_router
from app.bot.handlers.myorders import router as myorders_router

__all__ = [
    "start_router",
    "registration_router",
    "parcel_router",
    "tariffs_router",
    "subscription_router",
    "tracking_router",
    "batch_router",
    "profile_router",
    "help_router",
    "admin_router",
    "ai_router",
    "account_router",
    "convert_router",
    "shop_router",
    "webapp_router",
    "stats_router",
    "torgi_router",
    "clip_router",
    "myorders_router",
]
