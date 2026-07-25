"""API: админ-эндпоинты.

Полноценная админ-панель: статистика, пользователи, заказы, рассылка.
Защита: X-Admin-Key — SHA256 от telegram_id админа (см. ADMIN_IDS в .env).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import async_session_factory
from app.repositories import (
    PaymentRepo,
    SubscriptionRepo,
    UserRepo,
)
from app.services.account_pool import AccountPool
from app.services.shop_orders import ShopOrderStore

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── Пути к JSON-хранилищам ────────────────────────────────────
_BASE = Path(__file__).resolve().parents[2]


# ── Аутентификация ─────────────────────────────────────────────
def _hash_admin_id(tid: int) -> str:
    """SHA256 от telegram_id админа."""
    return hashlib.sha256(str(tid).encode()).hexdigest()


def _check_admin(request: Request) -> None:
    """Проверить X-Admin-Key в заголовке.

    Ключ — SHA256 от любого telegram_id из ADMIN_IDS.
    """
    # В dev-режиме без ADMIN_IDS — пропускаем всех
    if not settings.ADMIN_IDS:
        return

    key = request.headers.get("x-admin-key", "")
    if not key:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Key header")

    valid = any(hmac.compare_digest(key, _hash_admin_id(tid)) for tid in settings.ADMIN_IDS)
    if not valid:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# ── Вспомогательные ────────────────────────────────────────────
async def _get_repos():
    """Создать сессию и репозитории для одного запроса."""
    session = async_session_factory()
    try:
        repos = {
            "user": UserRepo(session),
            "payment": PaymentRepo(session),
            "subscription": SubscriptionRepo(session),
        }
        yield repos
        await session.commit()
    finally:
        await session.close()


def _get_shop_store() -> ShopOrderStore:
    return ShopOrderStore(_BASE / "shop_orders.json")


def _get_account_pool() -> AccountPool:
    return AccountPool(_BASE / "account_pool.json")


# ── 1. Общая статистика ────────────────────────────────────────
@router.get("/stats")
async def admin_stats(
    request: Request,
    repos: dict = Depends(_get_repos),
):
    """Общая статистика: пользователи, подписки, заказы, выручка."""
    _check_admin(request)

    total_users = await repos["user"].get_total_count()
    active_users = await repos["user"].get_active_count()

    # Подписки
    subs = await repos["subscription"].get_all_active()
    active_subs = len(subs)

    # Платежи/заказы — статистика по успешным
    # Используем метод get_successful_count (если есть) или обходим
    total_revenue = 0
    total_payments = 0

    # Заказы магазина (JSON)
    shop_store = _get_shop_store()
    orders_data = shop_store._load() if hasattr(shop_store, "_load") else {}
    if not orders_data and hasattr(shop_store, "_load"):
        pass
    # Fallback — читаем файл напрямую
    orders_path = _BASE / "shop_orders.json"
    if orders_path.exists():
        try:
            raw = json.loads(orders_path.read_text(encoding="utf-8"))
            orders_data = raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError):
            orders_data = {}

    pending_orders = 0
    delivered_orders = 0
    for o in orders_data.values():
        status = o.get("status", "")
        if status in ("awaiting_payment", "payment_claimed"):
            pending_orders += 1
        elif status == "delivered":
            delivered_orders += 1
            total_revenue += o.get("price", 0)

    # Аккаунты NextGIS
    pool = _get_account_pool()
    pool_data = pool._load() if hasattr(pool, "_load") else {}
    free_accounts = sum(1 for a in pool_data.values() if a.get("status") == "free")
    assigned_accounts = sum(1 for a in pool_data.values() if a.get("status") == "assigned")


    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "blocked": total_users - active_users,
        },
        "subscriptions": {
            "active": active_subs,
        },
        "shop": {
            "pending_orders": pending_orders,
            "delivered_orders": delivered_orders,
            "total_revenue_rub": total_revenue,
        },
        "accounts": {
            "free": free_accounts,
            "assigned": assigned_accounts,
            "total": free_accounts + assigned_accounts,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── 2. Список пользователей ────────────────────────────────────
@router.get("/users")
async def admin_users(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    repos: dict = Depends(_get_repos),
):
    """Список пользователей с пагинацией."""
    _check_admin(request)

    offset = (page - 1) * per_page
    total = await repos["user"].get_total_count()
    users = await repos["user"].get_all_users(limit=per_page, offset=offset)

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "users": [
            {
                "telegram_id": u.telegram_id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_blocked": u.is_blocked,
                "daily_requests_used": u.daily_requests_used,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
            }
            for u in users
        ],
    }


# ── 3. Детально по пользователю ────────────────────────────────
@router.get("/users/{telegram_id}")
async def admin_user_detail(
    request: Request,
    telegram_id: int,
    repos: dict = Depends(_get_repos),
):
    """Детальная информация о пользователе."""
    _check_admin(request)

    user = await repos["user"].get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Подписки
    sub = await repos["subscription"].get_active(telegram_id)
    payments = await repos["payment"].get_user_payments(telegram_id, limit=10)

    return {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_blocked": user.is_blocked,
        "daily_requests_used": user.daily_requests_used,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        "registered_at": user.registered_at.isoformat() if hasattr(user, "registered_at") and user.registered_at else None,
        "active_subscription": {
            "plan_code": sub.plan_code if sub else None,
            "status": sub.status.value if sub and hasattr(sub.status, "value") else (sub.status if sub else None),
            "expires_at": sub.expires_at.isoformat() if sub else None,
        } if sub else None,
        "recent_payments": [
            {
                "id": str(p.id),
                "amount": float(p.amount),
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "plan_code": p.plan_code,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p in payments
        ],
    }


# ── 4. Заказы магазина ─────────────────────────────────────────
@router.get("/orders")
async def admin_shop_orders(
    request: Request,
    status: str | None = Query(None),
):
    """Список заказов магазина."""
    _check_admin(request)

    store = _get_shop_store()
    orders = store._load() if hasattr(store, "_load") else {}
    if not orders:
        # fallback
        path = _BASE / "shop_orders.json"
        if path.exists():
            try:
                orders = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                orders = {}

    result = list(orders.values())
    if status:
        result = [o for o in result if o.get("status") == status]

    # Сортируем по дате создания (сначала новые)
    result.sort(key=lambda o: o.get("created_at", ""), reverse=True)

    return {
        "total": len(result),
        "orders": [
            {
                "id": o.get("id"),
                "kind": o.get("kind"),
                "item_id": o.get("item_id"),
                "title": o.get("title"),
                "price": o.get("price"),
                "kopecks": o.get("kopecks"),
                "user_id": o.get("user_id"),
                "username": o.get("username"),
                "status": o.get("status"),
                "created_at": o.get("created_at"),
            }
            for o in result
        ],
    }


# ── 5. Подтвердить/отклонить заказ ─────────────────────────────
@router.post("/orders/{order_id}/confirm")
async def admin_confirm_order(
    request: Request,
    order_id: str,
):
    """Подтвердить заказ (статус → delivered)."""
    _check_admin(request)

    store = _get_shop_store()
    try:
        from app.services.shop_orders import STATUS_DELIVERED
        order = store.set_status(order_id, STATUS_DELIVERED)
    except Exception:
        # fallback — напрямую в JSON
        path = _BASE / "shop_orders.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if order_id not in raw:
                raise HTTPException(status_code=404, detail="Order not found")
            raw[order_id]["status"] = "delivered"
            raw[order_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            order = raw[order_id]
        else:
            raise HTTPException(status_code=404, detail="Order not found")

    return {"status": "ok", "order": {"id": order_id, "status": "delivered"}}


@router.post("/orders/{order_id}/reject")
async def admin_reject_order(
    request: Request,
    order_id: str,
):
    """Отклонить заказ (статус → rejected)."""
    _check_admin(request)

    path = _BASE / "shop_orders.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Orders file not found")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if order_id not in raw:
        raise HTTPException(status_code=404, detail="Order not found")

    raw[order_id]["status"] = "rejected"
    raw[order_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"status": "ok", "order": {"id": order_id, "status": "rejected"}}


# ── 6. Заблокировать/разблокировать пользователя ───────────────
@router.post("/users/{telegram_id}/block")
async def admin_block_user(
    request: Request,
    telegram_id: int,
    repos: dict = Depends(_get_repos),
):
    """Заблокировать пользователя."""
    _check_admin(request)
    user = await repos["user"].get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await repos["user"].block_user(telegram_id)
    return {"status": "ok", "telegram_id": telegram_id, "blocked": True}


@router.post("/users/{telegram_id}/unblock")
async def admin_unblock_user(
    request: Request,
    telegram_id: int,
    repos: dict = Depends(_get_repos),
):
    """Разблокировать пользователя."""
    _check_admin(request)
    user = await repos["user"].get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await repos["user"].unblock_user(telegram_id)
    return {"status": "ok", "telegram_id": telegram_id, "blocked": False}


# ── 7. Пул аккаунтов NextGIS ───────────────────────────────────
@router.get("/accounts")
async def admin_accounts(
    request: Request,
    status: str | None = Query(None),
):
    """Список аккаунтов NextGIS."""
    _check_admin(request)

    pool = _get_account_pool()
    accounts = pool._load() if hasattr(pool, "_load") else {}
    path = _BASE / "account_pool.json"
    if not accounts and path.exists():
        try:
            accounts = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            accounts = {}

    result = list(accounts.values())
    if status:
        result = [a for a in result if a.get("status") == status]

    return {
        "total": len(result),
        "accounts": [
            {
                "login": a.get("login"),
                "status": a.get("status"),
                "user_id": a.get("user_id"),
                "updated_at": a.get("updated_at"),
            }
            for a in result
        ],
    }


# ── 8. Состояние здоровья системы ──────────────────────────────
@router.get("/health")
async def admin_health(request: Request):
    """Проверка всех систем."""
    _check_admin(request)

    checks = {
        "database": False,
        "redis": False,
        "shop_orders_file": False,
        "account_pool_file": False,
    }

    # БД
    try:
        async with async_session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception:
        pass

    # Redis
    try:
        from app.integrations.redis_cache import RedisCache
        rc = RedisCache()
        await rc.set("health_check", "ok", ttl=5)
        val = await rc.get("health_check")
        checks["redis"] = val == "ok"
    except Exception:
        pass

    # Файлы
    checks["shop_orders_file"] = (_BASE / "shop_orders.json").exists()
    checks["account_pool_file"] = (_BASE / "account_pool.json").exists()

    all_ok = all(checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
