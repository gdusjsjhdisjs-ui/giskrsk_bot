"""Хранилище заказов магазина (JSON-файл, без миграций БД).

Простое и надёжное решение для ручного цикла продаж:
заказ создаётся при нажатии «Купить», подтверждается админом,
после подтверждения бот отправляет файл покупателю.

Когда подключится YooKassa — это хранилище легко заменить
на таблицу в основной БД.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parents[2]
_ORDERS_FILE = _BASE_DIR / "shop_orders.json"
_LOCK = asyncio.Lock()

# Статусы заказа
STATUS_AWAITING = "awaiting_payment"   # создан, ждём оплату
STATUS_CLAIMED = "payment_claimed"     # покупатель нажал «Я оплатил»
STATUS_DELIVERED = "delivered"         # админ подтвердил, файл отправлен
STATUS_REJECTED = "rejected"           # админ отклонил

STATUS_LABELS = {
    STATUS_AWAITING: "⏳ Ожидает оплату",
    STATUS_CLAIMED: "🟡 Оплата заявлена (ждёт проверки)",
    STATUS_DELIVERED: "✅ Выдан",
    STATUS_REJECTED: "❌ Отклонён",
}


def fmt_amount(price: int, kopecks: int = 0) -> str:
    """Сумма к оплате: «2 990,47 ₽» (копейки — код платежа)."""
    rub = f"{price:,}".replace(",", " ")
    return f"{rub},{kopecks:02d} ₽" if kopecks else f"{rub} ₽"


class ShopOrderStore:
    """Потокобезопасное JSON-хранилище заказов."""

    def __init__(self, path: Path | str = _ORDERS_FILE) -> None:
        self._path = Path(path)

    # ── внутренние ──────────────────────────────────────────────

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, orders: dict[str, dict[str, Any]]) -> None:
        self._path.write_text(
            json.dumps(orders, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── публичные ───────────────────────────────────────────────

    def create(
        self,
        item_id: str,
        user_id: int,
        username: str | None,
        price: int,
        title: str,
        kind: str = "shop",
    ) -> dict[str, Any]:
        """Создать заказ и вернуть его.

        kind: "shop" — товар из магазина, "subscription" — подписка.
        """
        order_id = uuid.uuid4().hex[:8].upper()
        with _LOCK:
            orders = self._load()
            # Копеечный код: уникальные копейки в сумме, чтобы платёж
            # было легко найти в банке (2 990,47 ₽ → код 47).
            used = {
                o.get("kopecks")
                for o in orders.values()
                if o.get("status") in (STATUS_AWAITING, STATUS_CLAIMED)
            }
            kopecks = next((k for k in range(1, 100) if k not in used), 0)
            if price <= 0:
                kopecks = 0
            order = {
                "id": order_id,
                "kind": kind,
                "item_id": item_id,
                "title": title,
                "price": price,
                "kopecks": kopecks,
                "user_id": user_id,
                "username": username or "",
                "status": STATUS_AWAITING,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            orders[order_id] = order
            self._save(orders)
        return order

    def get(self, order_id: str) -> dict[str, Any] | None:
        with _LOCK:
            return self._load().get(order_id)

    def set_status(self, order_id: str, status: str) -> dict[str, Any] | None:
        with _LOCK:
            orders = self._load()
            order = orders.get(order_id)
            if order is None:
                return None
            order["status"] = status
            order["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(orders)
            return order

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with _LOCK:
            orders = list(self._load().values())
        orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
        return orders[:limit]

    def set_meta(self, order_id: str, meta: dict) -> dict[str, Any] | None:
        """Сохранить доп. данные заказа (bbox, layer_id и т.д.)."""
        with _LOCK:
            orders = self._load()
            order = orders.get(order_id)
            if order is None:
                return None
            order["meta"] = meta
            order["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(orders)
            return order

    def has_active_order(self, user_id: int, item_id: str, kind: str = "shop") -> bool:
        """Есть ли активный заказ (защита от дублей)."""
        active_statuses = {"awaiting_payment", "payment_claimed"}
        with _LOCK:
            orders = self._load()
        return any(
            o.get("user_id") == user_id
            and o.get("item_id") == item_id
            and o.get("kind") == kind
            and o.get("status") in active_statuses
            for o in orders.values()
        )
