"""YooKassa API-клиент — интеграция с платёжным шлюзом ЮKassa.

Методы:
  - create_payment — создание нового платежа
  - get_payment_info — проверка статуса/данных платежа
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Исключения ──────────────────────────────────────────────────────────


class YooKassaError(Exception):
    """Ошибка взаимодействия с API ЮKassa."""


# ─── Клиент ──────────────────────────────────────────────────────────────


class YooKassaClient:
    """HTTP-клиент для YooKassa API v3.

    Использует Basic-аутентификацию (shop_id + secret_key).
    Все публичные методы — async.
    """

    def __init__(self) -> None:
        auth = httpx.BasicAuth(
            username=settings.YOOKASSA_SHOP_ID,
            password=settings.YOOKASSA_SECRET_KEY,
        )
        self._client = httpx.AsyncClient(
            base_url="https://api.yookassa.ru/v3",
            auth=auth,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        logger.info(
            "YooKassaClient инициализирован: shop_id=%s",
            settings.YOOKASSA_SHOP_ID,
        )

    # ─── Публичные методы API ──────────────────────────────────────────

    async def create_payment(
        self,
        amount: Decimal,
        currency: str = "RUB",
        description: str = "",
        return_url: str = "",
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """Создать новый платёж.

        Args:
            amount: Сумма платежа.
            currency: Валюта (по умолчанию RUB).
            description: Описание платежа (назначение).
            return_url: URL для редиректа после оплаты.
            idempotency_key: Ключ идемпотентности (если пустой —
                генерируется автоматически).

        Returns:
            Ответ YooKassa с confirmation_url, id и статусом.

        Raises:
            YooKassaError: При ошибке API.
        """
        url = "/payments"

        key = idempotency_key or str(uuid.uuid4())
        body: dict[str, Any] = {
            "amount": {
                "value": _format_amount(amount),
                "currency": currency,
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or settings.YOOKASSA_RETURN_URL,
            },
            "capture": True,
            "description": description,
        }

        try:
            response = await self._client.post(
                url,
                json=body,
                headers={"Idempotence-Key": key},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as exc:
            _raise_yookassa_error(exc)
        except httpx.RequestError as exc:
            raise YooKassaError(f"Сетевая ошибка YooKassa: {exc}") from exc

    async def get_payment_info(self, payment_id: str) -> dict[str, Any]:
        """Получить информацию о платеже.

        Args:
            payment_id: UUID платежа.

        Returns:
            Данные платежа (статус, сумма, даты и т.д.).

        Raises:
            YooKassaError: При ошибке API.
        """
        url = f"/payments/{payment_id}"

        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as exc:
            _raise_yookassa_error(exc)
        except httpx.RequestError as exc:
            raise YooKassaError(f"Сетевая ошибка YooKassa: {exc}") from exc

    async def close(self) -> None:
        """Закрытие HTTP-сессии."""
        await self._client.aclose()
        logger.info("YooKassaClient сессия закрыта")


# ─── Вспомогательные функции ──────────────────────────────────────────────


def _format_amount(amount: Decimal) -> str:
    """Форматирует Decimal в строку с двумя знаками после запятой.

    YooKassa требует ровно 2 десятичных знака для рублей.
    Пример: Decimal("100.50") → "100.50"
    """
    return f"{amount:.2f}"


def _raise_yookassa_error(exc: httpx.HTTPStatusError) -> None:
    """Преобразует HTTPStatusError в YooKassaError с телом ответа."""
    try:
        detail = exc.response.json()
    except Exception:
        detail = {"raw": exc.response.text[:500]}

    raise YooKassaError(
        f"YooKassa {exc.response.status_code}: {detail}",
    ) from exc
