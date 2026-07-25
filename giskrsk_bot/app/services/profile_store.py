"""Профили пользователей: имя, почта, телефон, согласие на рассылку.

Мини-CRM на JSON-файле (без миграций БД). Используется для:
- регистрации новых пользователей (/register);
- рекламной рассылки тем, кто дал согласие (/promo).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parents[2]
_PROFILES_FILE = _BASE_DIR / "user_profiles.json"
_LOCK = threading.Lock()


class ProfileStore:
    """Потокобезопасное JSON-хранилище профилей."""

    def __init__(self, path: Path | str = _PROFILES_FILE) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, profiles: dict[str, dict[str, Any]]) -> None:
        self._path.write_text(
            json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, user_id: int) -> dict[str, Any] | None:
        with _LOCK:
            return self._load().get(str(user_id))

    def upsert(self, user_id: int, **fields: Any) -> dict[str, Any]:
        with _LOCK:
            profiles = self._load()
            profile = profiles.get(str(user_id)) or {
                "user_id": user_id,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
            profile.update(fields)
            profile["updated_at"] = datetime.now(timezone.utc).isoformat()
            profiles[str(user_id)] = profile
            self._save(profiles)
        return profile

    def all_profiles(self) -> list[dict[str, Any]]:
        """Все профили (для фоновых проверок и статистики)."""
        with _LOCK:
            return list(self._load().values())

    def consented_ids(self) -> list[int]:
        """ID всех, кто согласился на рекламную рассылку."""
        with _LOCK:
            return [
                p["user_id"]
                for p in self._load().values()
                if p.get("promo_consent")
            ]

    def count(self) -> int:
        with _LOCK:
            return len(self._load())
