"""API: вебхуки от YooKassa."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, HTTPException

from app.services.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def get_processor(request: Request) -> WebhookProcessor:
    """Получить WebhookProcessor из state приложения."""
    processor = request.app.state.webhook_processor
    if not processor:
        raise HTTPException(status_code=503, detail="Webhook processor not initialized")
    return processor


@router.post("/yookassa")
async def yookassa_webhook(request: Request) -> dict:
    """Принять вебхук от YooKassa."""
    raw_body = (await request.body()).decode("utf-8")
    signature = request.headers.get("Authorization", "").replace("Bearer ", "")

    processor = get_processor(request)
    try:
        result = await processor.process(raw_body, signature)
        return result
    except Exception as e:
        logger.error("Webhook processing error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
