"""Integrations — внешние сервисы и клиенты для Telegram-бота «ГИС Красноярье»."""

from app.integrations.nextgis import NextGISClient, NextGISError, ParcelInfo, ZoneInfo
from app.integrations.yookassa import YooKassaClient, YooKassaError
from app.integrations.redis_cache import RedisCache
from app.integrations.telegram import TelegramClient
from app.integrations.geoservice import GeoServiceClient, ObjectInfo

__all__ = [
    "NextGISClient",
    "NextGISError",
    "ParcelInfo",
    "ZoneInfo",
    "YooKassaClient",
    "YooKassaError",
    "RedisCache",
    "TelegramClient",
    "GeoServiceClient",
    "ObjectInfo",
]
