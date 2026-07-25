"""API: админ-эндпоинты."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def admin_stats() -> dict:
    """Статистика (заглушка — будет подключена к репозиториям)."""
    return {"status": "ok", "message": "Admin API"}
