"""Service: parcel lookup via GeoService + NextGIS fallback."""

from __future__ import annotations

import logging
import re

from app.core.exceptions import InvalidCadastralNumberError
from app.integrations.geoservice import GeoServiceClient, ObjectInfo
from app.integrations.nextgis import NextGISClient
from app.integrations.redis_cache import RedisCache

logger = logging.getLogger(__name__)

CADNUM_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{6,7}:\d+$")


def normalize_cadnum(raw: str) -> str | None:
    cleaned = raw.replace(" ", "").replace("\t", "")
    cleaned = cleaned.replace("—", ":").replace("-", ":").replace("–", ":")
    return cleaned if CADNUM_PATTERN.match(cleaned) else None


class NotFoundError(Exception):
    pass


class ParcelService:
    """Parcel search via GeoService (PKK Rosreestr) + NextGIS fallback."""

    def __init__(
        self,
        geoservice: GeoServiceClient,
        nextgis: NextGISClient | None = None,
        redis: RedisCache | None = None,
    ) -> None:
        self.geoservice = geoservice
        self.nextgis = nextgis
        self.redis = redis

    async def search_by_cadnum(self, raw_cadnum: str) -> ObjectInfo:
        """Search parcel by cadastral number."""
        cadnum = normalize_cadnum(raw_cadnum)
        if not cadnum:
            raise InvalidCadastralNumberError(f"Invalid format: {raw_cadnum}")

        # Cache check
        if self.redis:
            cached = await self.redis.get_parcel_cache(cadnum)
            if cached:
                return ObjectInfo(**cached)

        # GeoService (no direct cadnum search, skip)
        # NextGIS fallback
        if self.nextgis:
            data = await self.nextgis.search_by_cadnum(cadnum)
            if data:
                fields = data.get("fields") or data.get("properties") or {}
                geom = data.get("geom") or data.get("geometry") or {}
                obj = ObjectInfo(
                    cadastral_number=cadnum,
                    area_m2=fields.get("area_m2") or fields.get("area"),
                    cadastral_value=fields.get("cadastral_value") or fields.get("cadastre_cost"),
                    permitted_use=fields.get("vri") or fields.get("permitted_use"),
                    coordinates={"lon": float(geom.get("x", 0)), "lat": float(geom.get("y", 0))} if geom.get("x") else None,
                    raw_data=data,
                )
                if self.redis:
                    await self.redis.set_parcel_cache(cadnum, obj.model_dump())
                return obj

        raise NotFoundError(f"Parcel {cadnum} not found. Need NextGIS Web token.")

    async def identify_by_point(self, lon: float, lat: float, types: str = "1,2,4,5,10") -> list[ObjectInfo]:
        """Find objects at coordinates via GeoService."""
        return await self.geoservice.identify_by_point(lon, lat, types)
