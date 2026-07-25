"""Мидлвар: проброс сервисов и репозиториев в хендлеры.

Фикс session-per-request: репозитории не садятся на одну сессию на всё время жизни бота.
На каждый Telegram-апдейт создаётся свежая сессия, после хендлера — commit или rollback.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ServiceInjectorMiddleware(BaseMiddleware):
    """Пробрасывает сервисы и репозитории в handler через data.

    session_factory — фабрика SQLAlchemy async_session_maker.
        Если передана, для каждого апдейта создаётся свежая сессия.
    repo_factories — словарь {name: callable(session) -> repo}.
        Если не переданы, repos будут пустым словарём.
    """

    def __init__(
        self,
        services: dict[str, Any] | None = None,
        repos: dict[str, Any] | None = None,
        session_factory: Any | None = None,
        repo_factories: dict[str, Any] | None = None,
    ) -> None:
        self.services = services or {}
        self._static_repos = repos or {}          # legacy: статичные репозитории
        self._session_factory = session_factory   # async_session_maker
        self._repo_factories = repo_factories or {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["services"] = self.services

        if self._session_factory and self._repo_factories:
            # Создаём свежую сессию на каждый апдейт
            async with self._session_factory() as session:
                data["repos"] = {
                    name: factory(session)
                    for name, factory in self._repo_factories.items()
                }
                try:
                    result = await handler(event, data)
                    await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
        else:
            # Фоллбэк: статичные репозитории (поллинг-режим, SQLite)
            data["repos"] = self._static_repos
            return await handler(event, data)
