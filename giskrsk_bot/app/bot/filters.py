from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.core.config import settings


class IsAdmin(BaseFilter):
    """Проверяет, является ли пользователь администратором.

    Работает как для Message, так и для CallbackQuery.
    """

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = event.from_user
        if user is None:
            return False
        return user.id in settings.ADMIN_IDS


class HasActiveSubscription(BaseFilter):
    """Проверяет наличие активной подписки у пользователя.

    Полная реализация будет после подключения PostgreSQL.
    Сейчас пропускает всех (JSON-хранилища подписок не используется).
    """

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return True  # TODO: real check via SubscriptionRepo on VPS


class IsNotBlocked(BaseFilter):
    """Проверяет, не заблокирован ли пользователь.

    Полная реализация будет после подключения PostgreSQL.
    """

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return True  # TODO: real check via UserRepo on VPS
