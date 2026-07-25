"""Картинки товаров магазина.

Админ отправляет боту фото с подписью «/set_photo id_товара» —
бот запоминает file_id картинки и показывает её в карточке товара.

Хранение: shop_photos.json (хранится только Telegram file_id,
сами картинки лежат на серверах Telegram — место не расходуется).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parents[2]
_PHOTOS_FILE = _BASE_DIR / "shop_photos.json"
_LOCK = threading.Lock()


class ShopPhotoStore:
    """Потокобезопасное JSON-хранилище картинок товаров."""

    def __init__(self, path: Path | str = _PHOTOS_FILE) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, photos: dict[str, str]) -> None:
        self._path.write_text(
            json.dumps(photos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, item_id: str) -> str | None:
        """file_id картинки товара или None."""
        with _LOCK:
            return self._load().get(item_id)

    def set(self, item_id: str, file_id: str) -> None:
        """Прикрепить/заменить картинку товара."""
        with _LOCK:
            photos = self._load()
            photos[item_id] = file_id
            self._save(photos)

    def remove(self, item_id: str) -> bool:
        """Убрать картинку товара."""
        with _LOCK:
            photos = self._load()
            if item_id not in photos:
                return False
            del photos[item_id]
            self._save(photos)
        return True
