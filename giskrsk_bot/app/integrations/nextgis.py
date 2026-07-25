"""NextGIS Web API client with session-based auth."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)
RETRY_DELAYS = [1, 2, 4, 8]
RETRY_MAX = 3



class NextGISError(Exception):
    pass


class ParcelInfo(BaseModel):
    cadastral_number: str
    zone_code: str | None = None
    zone_name: str | None = None
    vri: str | None = None
    area_m2: float | None = None
    cadastral_value: float | None = None
    coordinates: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None


class ZoneInfo(BaseModel):
    zone_code: str
    zone_name: str
    zone_description: str | None = None
    permitted_uses: list[str] = []
    conditional_permitted: list[str] = []
    auxiliary_uses: list[str] = []
    max_floors: int | None = None
    max_height_m: float | None = None
    min_parcel_size_m2: float | None = None
    max_build_percent: float | None = None


class NextGISClient:
    """NextGIS Web API client — session-based auth + Bearer token fallback."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._logged_in = False

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            self._client = httpx.AsyncClient(
                base_url=settings.NEXTGIS_BASE_URL or "https://zimin-maplive0000.nextgis.com",
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=limits,
            )
        return self._client

    async def login(self) -> None:
        """Log in to get session cookie for API access."""
        if self._logged_in:
            return
        try:
            r = await self.client.post(
                "/api/component/auth/login",
                json={"login": settings.NEXTGIS_LOGIN, "password": settings.NEXTGIS_PASSWORD},
            )
            if r.status_code == 200:
                self._logged_in = True
                logger.info("NextGIS Web: logged in as %s", settings.NEXTGIS_LOGIN)
            else:
                logger.warning("NextGIS Web login failed: %d", r.status_code)
        except Exception as e:
            logger.warning("NextGIS Web login error: %s", e)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Request with retry and auto-login."""
        await self.login()
        last_err = None
        for attempt in range(RETRY_MAX):
            try:
                r = await self.client.request(method, path, **kwargs)
                if r.status_code >= 500 and attempt < RETRY_MAX - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                return r
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_err = e
                if attempt < RETRY_MAX - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                raise NextGISError(f"Request failed after {RETRY_MAX} attempts") from last_err

    async def search_by_cadnum(self, cadnum: str) -> dict | None:
        """Search parcel by cadastral number via Cadaster API."""
        await self.login()
        try:
            r = await self._request(
                "GET", "/api/component/cadaster/request/by-id",
                params={"types": "1", "id": cadnum},
            )
            data = r.json()
            features = data.get("features", [])
            if features:
                return features[0]
        except Exception as e:
            logger.warning("search_by_cadnum error: %s", e)
        return None

    async def identify_by_point(self, lon: float, lat: float) -> list[dict]:
        """Identify objects at coordinates via Cadaster API."""
        await self.login()
        try:
            r = await self._request(
                "GET", "/api/component/cadaster/request/by-position",
                params={"lon": lon, "lat": lat, "types": "1,2,4,5,10"},
            )
            data = r.json()
            return data.get("features", [])
        except Exception as e:
            logger.warning("identify_by_point error: %s", e)
            return []

    async def get_layer_geojson(self, resource_id: int) -> dict:
        r = await self._request("GET", f"/api/resource/{resource_id}/geojson")
        return r.json()

    async def check_layer_version(self, resource_id: int) -> int:
        r = await self._request("GET", f"/api/resource/{resource_id}/feature/version/")
        return int(r.text.strip())

    async def get_layer_changes(self, resource_id: int, version_from: int) -> list[dict]:
        r = await self._request("GET", f"/api/resource/{resource_id}/feature/changes/check", params={"version": version_from})
        return r.json()

    async def register_user(self, login: str, password: str, display_name: str) -> dict:
        r = await self._request("POST", "/api/component/auth/register", json={"login": login, "password": password, "display_name": display_name})
        return r.json()

    async def get_current_user(self) -> dict:
        await self.login()
        r = await self._request("GET", "/api/component/auth/current_user")
        return r.json()

    async def health_check(self) -> bool:
        try:
            r = await self._request("GET", "/")
            return r.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
