"""GeoService (geoservices.nextgis.com) — API к данным Росреестра/ПКК.

Слои (raster XYZ):
  - ngrr1: Единицы кадастрового деления
  - ngrr2: Земельные участки
  - ngrr3: Зоны с особыми условиями использования территории

API methods:
  - objects/coordinates — поиск по координатам
  - objects/{id} — поиск по ID
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

GEO_BASE = "https://geoservices.nextgis.com"
API_KEY = "073b03cc7ee19378c5b78d9c0ad70890"


class ObjectInfo(BaseModel):
    """Информация об объекте (участок, здание, зона)."""
    id: int | None = None
    cadastral_number: str | None = None
    object_type: int | None = None  # 1=участок, 2=объект, 5=здание
    address: str | None = None
    area_m2: float | None = None
    cadastral_value: float | None = None
    category: str | None = None  # категория земель
    permitted_use: str | None = None  # ВРИ
    coordinates: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None


class GeoServiceClient:
    """Клиент для geoservices.nextgis.com (ПКК Росреестра)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            self._client = httpx.AsyncClient(
                base_url=GEO_BASE,
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=limits,
                params={"apikey": API_KEY},
            )
        return self._client

    async def identify_by_point(self, lon: float, lat: float, types: str = "1,2,4,5,10") -> list[ObjectInfo]:
        """Определить объекты в точке через GeoService.

        types: 1=участки, 2=объекты, 4=площадь, 5=здания, 10=зоны
        """
        try:
            r = await self.client.get(
                "/pkk/features/by_pos",
                params={"lat": lat, "lon": lon, "cache": "include", "types": types},
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                features = data.get("features", [])
                return [self._parse_object(f) for f in features]
            return []
        except Exception as e:
            logger.warning("GeoService by_pos error: %s", e)
            return []

    async def get_by_id(self, obj_id: int, obj_type: int = 1) -> ObjectInfo | None:
        """Получить объект по ID."""
        try:
            r = await self.client.get(
                "/pkk/features/by_id",
                params={"cache": "include", "type": obj_type, "id": obj_id},
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                return self._parse_object(data)
            return None
        except Exception as e:
            logger.warning("GeoService by_id error: %s", e)
            return None

    def _parse_object(self, data: dict) -> ObjectInfo:
        """Распарсить ответ API в ObjectInfo."""
        props = data.get("properties") or data.get("fields") or data
        geom = data.get("geometry") or data.get("geom") or {}

        return ObjectInfo(
            id=props.get("id"),
            cadastral_number=props.get("cadastral_number") or props.get("cn") or props.get("cadnum"),
            object_type=props.get("type") or props.get("object_type"),
            address=props.get("address") or props.get("address_name"),
            area_m2=props.get("area_m2") or props.get("area"),
            cadastral_value=props.get("cadastral_value") or props.get("cadastre_cost"),
            category=props.get("category") or props.get("category_name"),
            permitted_use=props.get("permitted_use") or props.get("vri") or props.get("usage"),
            coordinates=geom,
            raw_data=data,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
