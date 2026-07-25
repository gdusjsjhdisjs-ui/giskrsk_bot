"""Реферальная программа: «приведи друга — получи +7 дней подписки».

Каждый пользователь имеет ссылку вида t.me/бот?start=ref_<его_id>.
Когда приглашённый оплачивает первый заказ подписки, пригласившему
автоматически продлевается подписка на BONUS_DAYS дней.

Хранение: referrals.json рядом с ботом.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parents[2]
_REF_FILE = _BASE_DIR / "referrals.json"
_LOCK = threading.Lock()

BONUS_DAYS = 7


class ReferralStore:
    """Потокобезопасное JSON-хранилище рефералов."""

    def __init__(self, path: Path | str = _REF_FILE) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict[str, Any]) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_referrer(self, user_id: int, referrer_id: int) -> bool:
        """Привязать нового пользователя к пригласившему (однократно)."""
        if user_id == referrer_id:
            return False
        with _LOCK:
            data = self._load()
            users = data.setdefault("users", {})
            user = users.setdefault(str(user_id), {})
            if user.get("referred_by"):
                return False
            user["referred_by"] = referrer_id
            user["joined_at"] = datetime.now(timezone.utc).isoformat()
            referrer = users.setdefault(str(referrer_id), {})
            invited = referrer.setdefault("invited", [])
            if user_id not in invited:
                invited.append(user_id)
            self._save(data)
        return True

    def get_referrer(self, user_id: int) -> int | None:
        with _LOCK:
            user = self._load().get("users", {}).get(str(user_id), {})
        return user.get("referred_by")

    def invited_count(self, user_id: int) -> int:
        with _LOCK:
            user = self._load().get("users", {}).get(str(user_id), {})
        return len(user.get("invited", []))

    def try_reward(self, order_id: str) -> bool:
        """True, если за этот заказ бонус ещё не начислялся (и пометить)."""
        with _LOCK:
            data = self._load()
            rewarded = data.setdefault("rewarded_orders", [])
            if order_id in rewarded:
                return False
            rewarded.append(order_id)
            self._save(data)
        return True
