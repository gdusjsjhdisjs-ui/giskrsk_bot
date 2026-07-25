"""Пул готовых аккаунтов NextGIS (командные места).

Админ заранее создаёт аккаунты в команде NextGIS Web и добавляет их
в пул командой /add_account. Бот выдаёт свободные аккаунты при оплате.

Статусы:
- free     — свободен, можно выдавать;
- assigned — выдан клиенту;
- expired  — подписка клиента истекла: нужно сменить пароль в NextGIS
             и вернуть аккаунт в пул (/add_account логин новый_пароль).

Хранение: account_pool.json рядом с ботом.
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parents[2]
_POOL_FILE = _BASE_DIR / "account_pool.json"
_LOCK = asyncio.Lock()

STATUS_FREE = "free"
STATUS_ASSIGNED = "assigned"
STATUS_EXPIRED = "expired"


class AccountPool:
    """Потокобезопасное JSON-хранилище аккаунтов."""

    def __init__(self, path: Path | str = _POOL_FILE) -> None:
        self._path = Path(path)

    # ── внутренние ──────────────────────────────────────────────

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, accounts: dict[str, dict[str, Any]]) -> None:
        self._path.write_text(
            json.dumps(accounts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── публичные ───────────────────────────────────────────────

    def add(self, login: str, password: str) -> dict[str, Any]:
        """Добавить аккаунт или обновить пароль.

        Выданный клиенту аккаунт остаётся выданным (обновится только
        пароль), а «истёкший» после смены пароля снова становится free.
        """
        with _LOCK:
            accounts = self._load()
            account = accounts.get(login)
            if account and account.get("status") == STATUS_ASSIGNED:
                account["password"] = password
            else:
                account = {
                    "login": login,
                    "password": password,
                    "status": STATUS_FREE,
                    "user_id": None,
                    "order_id": None,
                }
            account["updated_at"] = self._now()
            accounts[login] = account
            self._save(accounts)
        return account

    def acquire(self, user_id: int, order_id: str) -> dict[str, Any] | None:
        """Занять первый свободный аккаунт. None — пул пуст."""
        with _LOCK:
            accounts = self._load()
            for account in accounts.values():
                if account.get("status") == STATUS_FREE:
                    account.update(
                        status=STATUS_ASSIGNED,
                        user_id=user_id,
                        order_id=order_id,
                        updated_at=self._now(),
                    )
                    self._save(accounts)
                    return account
        return None

    def release(self, login: str) -> bool:
        """Вернуть аккаунт в пул (после смены пароля в NextGIS!)."""
        with _LOCK:
            accounts = self._load()
            account = accounts.get(login)
            if account is None:
                return False
            account.update(
                status=STATUS_FREE,
                user_id=None,
                order_id=None,
                updated_at=self._now(),
            )
            self._save(accounts)
        return True

    def mark_expired(self, login: str) -> bool:
        """Пометить аккаунт истёкшим (нужно сменить пароль и вернуть в пул)."""
        with _LOCK:
            accounts = self._load()
            account = accounts.get(login)
            if account is None:
                return False
            account.update(status=STATUS_EXPIRED, updated_at=self._now())
            self._save(accounts)
        return True

    def find_by_user(self, user_id: int) -> dict[str, Any] | None:
        """Найти аккаунт, выданный этому клиенту."""
        with _LOCK:
            for account in self._load().values():
                if (
                    account.get("user_id") == user_id
                    and account.get("status") == STATUS_ASSIGNED
                ):
                    return account
        return None

    def list_all(self) -> list[dict[str, Any]]:
        with _LOCK:
            return list(self._load().values())

    def free_count(self) -> int:
        with _LOCK:
            return sum(
                1
                for a in self._load().values()
                if a.get("status") == STATUS_FREE
            )
