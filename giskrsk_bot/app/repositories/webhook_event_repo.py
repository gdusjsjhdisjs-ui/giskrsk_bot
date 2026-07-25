"""Репозиторий событий вебхуков (защита от дублей)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaymentWebhookEvent


class WebhookEventRepo:
    """CRUD для таблицы payment_webhook_events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        provider: str,
        event_hash: str,
        external_payment_id: str | None = None,
        event_type: str | None = None,
        payload: dict | None = None,
    ) -> PaymentWebhookEvent:
        """Создать запись о входящем вебхуке."""
        event = PaymentWebhookEvent(
            provider=provider,
            event_hash=event_hash,
            external_payment_id=external_payment_id,
            event_type=event_type,
            payload=payload,
            processing_status="received",
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def get_by_hash(self, provider: str, event_hash: str) -> PaymentWebhookEvent | None:
        """Найти вебхук по хэшу (проверка на дубликат)."""
        stmt = select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == provider,
            PaymentWebhookEvent.event_hash == event_hash,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_payment_id(self, external_payment_id: str) -> list[PaymentWebhookEvent]:
        """Найти все вебхуки для платежа."""
        stmt = (
            select(PaymentWebhookEvent)
            .where(PaymentWebhookEvent.external_payment_id == external_payment_id)
            .order_by(PaymentWebhookEvent.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, event_id: UUID, status: str, error: str | None = None) -> None:
        """Обновить статус обработки вебхука."""
        stmt = select(PaymentWebhookEvent).where(PaymentWebhookEvent.id == event_id)
        result = await self.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.processing_status = status
            if error:
                event.error_message = error
            await self.session.commit()
