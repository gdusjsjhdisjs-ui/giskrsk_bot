"""Репозиторий пользователей."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepo:
    """CRUD для таблицы users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, telegram_id: int, username: str | None = None, full_name: str | None = None) -> User:
        """Получить пользователя или создать нового."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, username=username, full_name=full_name)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        else:
            # Обновляем метаданные при каждом входе
            if username and user.username != username:
                user.username = username
            if full_name and user.full_name != full_name:
                user.full_name = full_name
            user.last_seen_at = func.now()
            await self.session.commit()
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Получить пользователя по Telegram ID."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_role(self, telegram_id: int, role: str) -> None:
        """Обновить роль пользователя."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.role = role
            await self.session.commit()

    async def update_daily_requests(self, telegram_id: int) -> int:
        """Обновить счётчик дневных запросов. Возвращает новое значение."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return 0
        today = date.today()
        if user.daily_requests_date != today:
            user.daily_requests_used = 1
            user.daily_requests_date = today
        else:
            user.daily_requests_used += 1
        await self.session.commit()
        return user.daily_requests_used

    async def get_all_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        """Получить всех пользователей (для админки)."""
        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_count(self) -> int:
        """Общее количество пользователей."""
        stmt = select(func.count()).select_from(User)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_active_count(self) -> int:
        """Количество активных пользователей (не заблокированных)."""
        stmt = select(func.count()).select_from(User).where(User.is_blocked == False)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def block_user(self, telegram_id: int) -> None:
        """Заблокировать пользователя."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.is_blocked = True
            await self.session.commit()

    async def unblock_user(self, telegram_id: int) -> None:
        """Разблокировать пользователя."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.is_blocked = False
            await self.session.commit()
