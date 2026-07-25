"""Репозиторий платежей."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment


class PaymentRepo:
    """CRUD для таблицы payments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        telegram_id: int,
        plan_code: str,
        amount: float,
        idempotency_key: str,
        currency: str = "RUB",
        provider: str = "yookassa",
    ) -> Payment:
        """Создать запись о платеже."""
        payment = Payment(
            telegram_id=telegram_id,
            provider=provider,
            plan_code=plan_code,
            amount=amount,
            currency=currency,
            status="pending",
            idempotency_key=idempotency_key,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Получить платеж по ID."""
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        """Получить платеж по ключу идемпотентности."""
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_payment_id: str) -> Payment | None:
        """Получить платеж по ID из YooKassa."""
        stmt = select(Payment).where(Payment.external_payment_id == external_payment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_external_info(
        self,
        payment_id: UUID,
        external_payment_id: str,
        confirmation_url: str,
        provider_payload: dict | None = None,
    ) -> None:
        """Обновить внешние данные платежа (после создания в YooKassa)."""
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await self.session.execute(stmt)
        payment = result.scalar_one_or_none()
        if payment:
            payment.external_payment_id = external_payment_id
            payment.confirmation_url = confirmation_url
            if provider_payload:
                payment.provider_payload = provider_payload
            await self.session.commit()

    async def update_status(self, payment_id: UUID, status: str) -> None:
        """Обновить статус платежа."""
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await self.session.execute(stmt)
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = status
            if status == "succeeded":
                payment.paid_at = func.now()
            await self.session.commit()

    async def get_user_payments(self, telegram_id: int, limit: int = 20) -> list[Payment]:
        """Получить платежи пользователя."""
        stmt = (
            select(Payment)
            .where(Payment.telegram_id == telegram_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_revenue(self) -> float:
        """Общая выручка по успешным платежам."""
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "succeeded")
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def get_successful_count(self) -> int:
        """Количество успешных платежей."""
        stmt = select(func.count()).select_from(Payment).where(Payment.status == "succeeded")
        result = await self.session.execute(stmt)
        return result.scalar() or 0
