"""Геопространственный клиппинг GeoJSON по bounding box.

Депенденсия: shapely>=2.0 (лёгкая, без GDAL).
Запускать через asyncio.to_thread() — не блокирует event loop.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import box as shapely_box
    from shapely.geometry import mapping, shape
    from shapely.validation import make_valid
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False


def haversine_km2(minlon: float, minlat: float, maxlon: float, maxlat: float) -> float:
    """Площадь прямоугольника в км² через формулу Гаверсина."""
    R = 6371.0
    lat1 = math.radians(minlat)
    lat2 = math.radians(maxlat)
    lon1 = math.radians(minlon)
    lon2 = math.radians(maxlon)
    h = R * (lat2 - lat1)
    mid_lat = (lat1 + lat2) / 2
    w = R * math.cos(mid_lat) * (lon2 - lon1)
    return abs(h * w)


def clip_geojson_sync(
    source_path: Path,
    bbox: tuple,
    output_path: Path,
) -> dict[str, Any]:
    """
    Обрезает GeoJSON по bbox. Возвращает статистику.
    Запускать через asyncio.to_thread().
    """
    if not SHAPELY_OK:
        raise RuntimeError(
            "Модуль shapely не установлен. "
            "Добавьте shapely>=2.0 в requirements.txt и перезапустите бот."
        )

    minlon, minlat, maxlon, maxlat = bbox
    clip_box = shapely_box(minlon, minlat, maxlon, maxlat)
    area_km2 = haversine_km2(*bbox)

    with open(source_path, encoding="utf-8") as f:
        data = json.load(f)

    clipped_features: list[dict] = []
    skipped = 0

    for feature in data.get("features", []):
        try:
            geom = make_valid(shape(feature["geometry"]))
            if not geom.intersects(clip_box):
                continue
            clipped_geom = geom.intersection(clip_box)
            if clipped_geom.is_empty:
                continue
            new_feature = {
                "type": "Feature",
                "properties": feature.get("properties") or {},
                "geometry": mapping(clipped_geom),
            }
            clipped_features.append(new_feature)
        except Exception:
            skipped += 1
            continue

    result = {
        "type": "FeatureCollection",
        "features": clipped_features,
    }
    if "crs" in data:
        result["crs"] = data["crs"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    return {
        "feature_count": len(clipped_features),
        "skipped": skipped,
        "area_km2": round(area_km2, 2),
        "file_size_kb": output_path.stat().st_size // 1024,
        "output_path": str(output_path),
    }
