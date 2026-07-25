"""SQLAlchemy declarative base for ГИС Красноярье."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    __model_marker__: bool = True  # introspection hint
