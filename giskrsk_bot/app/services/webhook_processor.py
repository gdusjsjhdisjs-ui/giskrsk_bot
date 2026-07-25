"""Обработчик вебхуков от YooKassa (идемпотентный)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from app.core.config import settings
from app.repositories.payment_repo import PaymentRepo
from app.repositories.webhook_event_repo import WebhookEventRepo
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """Обработка входящих вебхуков YooKassa с защитой от дублей."""

    def __init__(
        self,
        webhook_event_repo: WebhookEventRepo,
        payment_repo: PaymentRepo,
        subscription_service: SubscriptionService,
    ) -> None:
        self.webhook_event_repo = webhook_event_repo
        self.payment_repo = payment_repo
        self.subscription_service = subscription_service

    def _compute_event_hash(self, raw_body: str) -> str:
        """SHA256 тела запроса для дедупликации."""
        return hashlib.sha256(raw_body.encode("utf-8")).hexdigest()

    def _verify_signature(self, raw_body: str, signature: str | None) -> bool:
        """Проверить подпись YooKassa (опционально)."""
        if not signature:
            logger.warning("No signature provided, skipping verification")
            return True
        expected = hmac.new(
            settings.YOOKASSA_SECRET_KEY.encode("utf-8"),
            raw_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def process(self, raw_body: str, signature: str | None = None) -> dict:
        """Обработать входящий вебхук."""
        event_hash = self._compute_event_hash(raw_body)

        # 1. Дедупликация
        existing = await self.webhook_event_repo.get_by_hash("yookassa", event_hash)
        if existing:
            logger.info("Duplicate webhook ignored: %s", event_hash)
            return {"status": "ignored", "reason": "duplicate"}

        # 2. Парсинг
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in webhook: %s", e)
            return {"status": "failed", "reason": "invalid_json"}

        event_type = payload.get("event", "")
        event_object = payload.get("object", {})
        external_payment_id = event_object.get("id", "")

        # 3. Сохраняем событие
        event = await self.webhook_event_repo.create(
            provider="yookassa",
            event_hash=event_hash,
            external_payment_id=external_payment_id,
            event_type=event_type,
            payload=payload,
        )

        # 4. Обработка по типу события
        try:
            if event_type == "payment.succeeded":
                await self._handle_succeeded(external_payment_id)
                await self.webhook_event_repo.update_status(event.id, "processed")
            elif event_type == "payment.canceled":
                await self._handle_canceled(external_payment_id)
                await self.webhook_event_repo.update_status(event.id, "processed")
            else:
                logger.info("Unknown event type: %s", event_type)
                await self.webhook_event_repo.update_status(event.id, "ignored")
        except Exception as e:
            logger.error("Webhook processing error: %s", e)
            await self.webhook_event_repo.update_status(event.id, "failed", str(e))
            return {"status": "failed", "reason": str(e)}

        return {"status": "processed", "event_type": event_type}

    async def _handle_succeeded(self, external_payment_id: str) -> None:
        """Обработать успешный платёж."""
        payment = await self.payment_repo.get_by_external_id(external_payment_id)
        if not payment:
            logger.warning("Payment not found for external_id: %s", external_payment_id)
            return

        if payment.status == "succeeded":
            logger.info("Payment already succeeded: %s", payment.id)
            return

        # Обновляем статус
        await self.payment_repo.update_status(payment.id, "succeeded")

        # Активируем подписку
        await self.subscription_service.activate(
            telegram_id=payment.telegram_id,
            plan_code=payment.plan_code,
            payment_id=payment.id,
        )

        logger.info("Subscription activated for user %s, plan %s", payment.telegram_id, payment.plan_code)

    async def _handle_canceled(self, external_payment_id: str) -> None:
        """Обработать отменённый платёж."""
        payment = await self.payment_repo.get_by_external_id(external_payment_id)
        if not payment:
            logger.warning("Payment not found for external_id: %s", external_payment_id)
            return

        await self.payment_repo.update_status(payment.id, "canceled")
        logger.info("Payment canceled: %s", payment.id)
