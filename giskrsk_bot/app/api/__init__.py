"""API __init__."""

from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router
from app.api.admin_api import router as admin_router

__all__ = ["health_router", "webhooks_router", "admin_router"]
