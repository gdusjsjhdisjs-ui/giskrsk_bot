"""Database session with SQLite support for local development."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


if settings.USE_SQLITE:
    logger.info("USE_SQLITE=True — using SQLite (dev mode)")
    engine = create_async_engine(
        "sqlite+aiosqlite:///./webgis_dev.db",
        echo=False,
    )
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
else:
    logger.info("Using PostgreSQL")
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
