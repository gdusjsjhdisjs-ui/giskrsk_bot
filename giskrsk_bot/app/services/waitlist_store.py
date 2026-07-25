"""Лист ожидания: клиенты, которым не хватило свободных аккаунтов.

Когда пул пуст, бот записывает клиента в waitlist.json. Как только
админ пополняет пул (/add_account), бот уведомляет всех ожидающих.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE_DIR = Path(__file__).resolve().parents[2]
_WAITLIST_FILE = _BASE_DIR / "waitlist.json"
_LOCK = threading.Lock()


class WaitlistStore:
    """Потокобезопасное JSON-хранилище листа ожидания."""

    def __init__(self, path: Path | str = _WAITLIST_FILE) -> None:
        self._path = Path(path)

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: list[dict[str, Any]]) -> None:
        self._path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, user_id: int, username: str | None, wanted: str = "") -> bool:
        """Добавить клиента (без дублей). True — если добавлен."""
        with _LOCK:
            entries = self._load()
            if any(e.get("user_id") == user_id for e in entries):
                return False
            entries.append(
                dict(
                    user_id=user_id,
                    username=username,
                    wanted=wanted,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            self._save(entries)
        return True

    def pop_all(self) -> list[dict[str, Any]]:
        """Забрать и очистить весь список."""
        with _LOCK:
            entries = self._load()
            self._save([])
        return entries

    def count(self) -> int:
        with _LOCK:
            return len(self._load())
