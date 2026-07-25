"""API: health check."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Проверка работоспособности сервиса."""
    return {"status": "ok", "service": "gis-krsk-bot"}
