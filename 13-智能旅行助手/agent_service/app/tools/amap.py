"""高德数据源适配：配了 Key 走 REST，未配 Key 走确定性样例数据。

后续要切换 MCP（stdio / Streamable HTTP）时，只需在这里换实现，
上层节点与数据模型不用动。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app import mock_data
from app.settings import Settings

logger = logging.getLogger(__name__)


class AmapClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mock = settings.use_mock_tools
        self._http = httpx.AsyncClient(base_url=settings.amap_rest_base, timeout=15.0)
        self._poi_cache: dict[str, list[dict[str, Any]]] = {}

    @property
    def mock(self) -> bool:
        return self._mock

    async def close(self) -> None:
        await self._http.aclose()

    async def search_attractions(self, city: str, keywords: str) -> list[dict[str, Any]]:
        if self._mock:
            await asyncio.sleep(0.3)
            return mock_data.mock_attractions(city)
        kw = keywords.strip() or "景点"
        pois = await self._text_search(city, f"{kw} 景点", types="110000")
        return [self._to_attraction(p) for p in pois]

    async def search_hotels(self, city: str, accommodation: str) -> list[dict[str, Any]]:
        if self._mock:
            await asyncio.sleep(0.2)
            return mock_data.mock_hotels(city)
        kw = accommodation.strip() or "酒店"
        pois = await self._text_search(city, kw, types="100000")
        return [self._to_hotel(p) for p in pois]

    async def query_weather(self, city: str, dates: list[str]) -> list[dict[str, Any]]:
        if self._mock:
            await asyncio.sleep(0.15)
            return mock_data.mock_weather(city, dates)

        cache_key = f"weather:{city}:{dates[0]}"
        if cache_key in self._poi_cache:
            return self._poi_cache[cache_key]

        data = await self._get(
            "/v3/weather/weatherInfo",
            {"city": city, "extensions": "all"},
        )
        forecasts = data.get("forecasts") or []
        casts = forecasts[0].get("casts", []) if forecasts else []
        wanted = set(dates)
        result = [
            {
                "date": c.get("date", ""),
                "day_weather": c.get("dayweather", ""),
                "night_weather": c.get("nightweather", ""),
                "day_temp": int(c.get("daytemp", 0) or 0),
                "night_temp": int(c.get("nighttemp", 0) or 0),
                "wind": f"{c.get('daywind', '')} {c.get('daypower', '')}".strip(),
            }
            for c in casts
            if c.get("date") in wanted
        ]
        self._poi_cache[cache_key] = result
        return result

    async def _text_search(self, city: str, keywords: str, types: str) -> list[dict[str, Any]]:
        cache_key = f"poi:{city}:{keywords}:{types}"
        if cache_key in self._poi_cache:
            return self._poi_cache[cache_key]
        data = await self._get(
            "/v3/place/text",
            {"city": city, "keywords": keywords, "types": types, "offset": 10, "page": 1, "extensions": "all"},
        )
        pois = data.get("pois") or []
        self._poi_cache[cache_key] = pois
        return pois

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "key": self._settings.amap_api_key, "output": "json"}
        resp = await self._http.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        if str(data.get("status")) != "1":
            raise RuntimeError(f"高德接口返回错误: {data.get('info')}")
        return data

    @staticmethod
    def _to_attraction(poi: dict[str, Any]) -> dict[str, Any]:
        lng, lat = _split_location(poi.get("location"))
        biz = poi.get("biz_ext") or {}
        return {
            "name": poi.get("name", ""),
            "address": poi.get("address") or poi.get("adname", ""),
            "visit_duration": "",
            "description": poi.get("type", ""),
            "ticket_price": float(biz.get("cost") or 0),
            "latitude": lat,
            "longitude": lng,
        }

    @staticmethod
    def _to_hotel(poi: dict[str, Any]) -> dict[str, Any]:
        lng, lat = _split_location(poi.get("location"))
        biz = poi.get("biz_ext") or {}
        return {
            "name": poi.get("name", ""),
            "address": poi.get("address") or poi.get("adname", ""),
            "price_per_night": float(biz.get("cost") or 0),
            "rating": str(biz.get("rating") or "暂无"),
        }


def _split_location(location: str | None) -> tuple[float | None, float | None]:
    if not location or "," not in location:
        return None, None
    lng, lat = location.split(",", 1)
    return float(lng), float(lat)
