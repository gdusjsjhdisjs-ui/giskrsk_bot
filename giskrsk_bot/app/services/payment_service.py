"""Сервис платежей: создание, проверка статуса."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import PaymentError
from app.integrations.yookassa import YooKassaClient
from app.repositories.payment_repo import PaymentRepo
from app.repositories.subscription_repo import SubscriptionRepo
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

# Маппинг: план → цена, длительность в днях
PLAN_PRICES: dict[str, int] = {
    "basic_30d": settings.TARIFF_BASIC_30D_PRICE,
    "pro_30d": settings.TARIFF_PRO_30D_PRICE,
    "pro_90d": settings.TARIFF_PRO_90D_PRICE,
    "year": settings.TARIFF_YEAR_PRICE,
}

PLAN_DURATIONS: dict[str, int] = {
    "basic_30d": 30,
    "pro_30d": 30,
    "pro_90d": 90,
    "year": 365,
}

PLAN_DESCRIPTIONS: dict[str, str] = {
    "basic_30d": "ГИС Красноярье — Basic на 30 дней",
    "pro_30d": "ГИС Красноярье — Pro на 30 дней",
    "pro_90d": "ГИС Красноярье — Pro на 90 дней",
    "year": "ГИС Красноярье — Pro на 12 месяцев",
}


class PaymentService:
    """Создание и проверка платежей через YooKassa."""

    def __init__(
        self,
        yookassa: YooKassaClient,
        payment_repo: PaymentRepo,
        subscription_service: SubscriptionService,
    ) -> None:
        self.yookassa = yookassa
        self.payment_repo = payment_repo
        self.subscription_service = subscription_service

    def _make_idempotency_key(self, telegram_id: int, plan_code: str) -> str:
        """Создать ключ идемпотентности."""
        raw = f"{telegram_id}:{plan_code}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def create_payment(self, telegram_id: int, plan_code: str) -> dict:
        """Создать платеж на оплату подписки."""
        if plan_code not in PLAN_PRICES:
            raise PaymentError(f"Неизвестный тариф: {plan_code}")

        amount = Decimal(str(PLAN_PRICES[plan_code]))
        description = PLAN_DESCRIPTIONS[plan_code]
        idempotency_key = self._make_idempotency_key(telegram_id, plan_code)

        # Создаём запись в БД
        payment = await self.payment_repo.create(
            telegram_id=telegram_id,
            plan_code=plan_code,
            amount=float(amount),
            idempotency_key=idempotency_key,
        )

        # Отправляем в YooKassa
        try:
            result = await self.yookassa.create_payment(
                amount=amount,
                description=description,
                idempotency_key=idempotency_key,
            )
        except Exception as e:
            logger.error("YooKassa create_payment failed: %s", e)
            await self.payment_repo.update_status(payment.id, "canceled")
            raise PaymentError(f"Ошибка создания платежа: {e}") from e

        # Обновляем внешние данные
        external_id = result.get("id", "")
        confirmation_url = (
            result.get("confirmation", {}).get("confirmation_url", "")
        )
        await self.payment_repo.update_external_info(
            payment_id=payment.id,
            external_payment_id=external_id,
            confirmation_url=confirmation_url,
            provider_payload=result,
        )

        return {
            "payment_id": str(payment.id),
            "external_payment_id": external_id,
            "confirmation_url": confirmation_url,
            "amount": float(amount),
            "description": description,
        }

    async def check_payment(self, payment_id: UUID) -> dict:
        """Проверить статус платежа и обновить подписку если успешно."""
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise PaymentError("Платёж не найден")

        # Уже успешен — возвращаем
        if payment.status == "succeeded":
            return {"status": "succeeded", "payment_id": str(payment_id)}

        # Проверяем в YooKassa
        if payment.external_payment_id:
            try:
                info = await self.yookassa.get_payment_info(payment.external_payment_id)
                yoo_status = info.get("status", "")
            except Exception as e:
                logger.error("YooKassa check failed: %s", e)
                return {"status": payment.status, "payment_id": str(payment_id), "error": str(e)}
        else:
            return {"status": payment.status, "payment_id": str(payment_id)}

        if yoo_status == "succeeded":
            await self.payment_repo.update_status(payment.id, "succeeded")
            # Активируем подписку
            await self.subscription_service.activate(
                telegram_id=payment.telegram_id,
                plan_code=payment.plan_code,
                payment_id=payment.id,
            )
            return {"status": "succeeded", "payment_id": str(payment_id)}
        elif yoo_status in ("canceled", "expired"):
            await self.payment_repo.update_status(payment.id, "canceled")
            return {"status": "canceled", "payment_id": str(payment_id)}

        return {"status": yoo_status, "payment_id": str(payment_id)}

    async def get_user_payments(self, telegram_id: int, limit: int = 20) -> list:
        """История платежей пользователя."""
        payments = await self.payment_repo.get_user_payments(telegram_id, limit)
        return [
            {
                "id": str(p.id),
                "plan_code": p.plan_code,
                "amount": float(p.amount),
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p in payments
        ]
