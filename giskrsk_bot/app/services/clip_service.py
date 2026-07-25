"""Сервис клиппинга: расчёт цены, выполнение клипа, пути файлов.

Правило цены: area_km2 * CLIP_PRICE_PER_KM2, но не меньше shop_price * CLIP_MIN_MULTIPLIER.
Клип всегда дороже полного файла в магазине.
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any

from app.core.config import settings

_BASE_DIR = Path(__file__).resolve().parents[2]

# Каталог слоёв доступных для клиппинга.
# Положите полные GeoJSON в shop_files/<name>_full.geojson
CLIP_LAYERS: dict[str, dict[str, Any]] = {
    "pzz_krsk": {
        "name": "ПЗЗ Красноярск",
        "file": "shop_files/pzz_krsk_full.geojson",
        "shop_price": 5000,
        "area_km2": 400,
    },
    "pzz_emel": {
        "name": "ПЗЗ Емельяново",
        "file": "shop_files/pzz_emel_full.geojson",
        "shop_price": 3000,
        "area_km2": 180,
    },
    "pzz_divn": {
        "name": "ПЗЗ Дивногорск",
        "file": "shop_files/pzz_divn_full.geojson",
        "shop_price": 3000,
        "area_km2": 50,
    },
    "pzz_sosn": {
        "name": "ПЗЗ Сосновоборск",
        "file": "shop_files/pzz_sosn_full.geojson",
        "shop_price": 3000,
        "area_km2": 35,
    },
}


def calculate_clip_price(area_km2: float, layer_id: str) -> int:
    """Цена клипа: всегда дороже полного файла в магазине."""
    layer = CLIP_LAYERS.get(layer_id, {})
    shop_price = layer.get("shop_price", 0)

    raw = area_km2 * settings.CLIP_PRICE_PER_KM2
    raw = max(raw, settings.CLIP_MIN_PRICE)

    # Гарантия: клип >= shop_price * CLIP_MIN_MULTIPLIER
    if shop_price:
        floor_price = math.ceil(shop_price * settings.CLIP_MIN_MULTIPLIER)
        raw = max(raw, floor_price)

    return int(math.ceil(raw / 10) * 10)  # округляем до 10 ₽


def get_clip_source_path(layer_id: str) -> Path | None:
    layer = CLIP_LAYERS.get(layer_id)
    if not layer:
        return None
    return _BASE_DIR / layer["file"]


def get_clip_output_path(order_id: str, layer_id: str) -> Path:
    return _BASE_DIR / "clip_files" / f"clip_{layer_id}_{order_id}.geojson"


async def do_clip(
    order_id: str,
    layer_id: str,
    bbox: tuple,
) -> dict[str, Any]:
    """Выполнить клиппинг асинхронно (в thread pool)."""
    from tools.clip_geodata import clip_geojson_sync

    source = get_clip_source_path(layer_id)
    if not source or not source.exists():
        raise FileNotFoundError(
            f"Исходный GeoJSON файл слоя '{layer_id}' не найден.\n"
            f"Положите файл в: {source}"
        )

    output = get_clip_output_path(order_id, layer_id)
    return await asyncio.to_thread(clip_geojson_sync, source, bbox, output)


def format_price_msg(area_km2: float, layer_id: str, price: int) -> str:
    """Сообщение с ценой для пользователя."""
    layer = CLIP_LAYERS.get(layer_id, {})
    name = layer.get("name", layer_id)
    shop_price = layer.get("shop_price", 0)
    area_total = layer.get("area_km2", "?")
    rate = settings.CLIP_PRICE_PER_KM2

    price_fmt = f"{price:,}".replace(",", " ")
    shop_fmt = f"{shop_price:,}".replace(",", " ")

    return (
        f"│ Площадь области: <b>{area_km2:.1f} км²</b>\n"
        f"│ Цена клипа: <b>{price_fmt} ₽</b>\n"
        f"│ ({rate} ₽/км², мин. {settings.CLIP_MIN_MULTIPLIER:.0f}x от магазина)\n\n"
        f"└ Для сравнения: <b>'{name}' целиком</b>\n"
        f"  в магазине = {shop_fmt} ₽ ({area_total} км²)"
    )
